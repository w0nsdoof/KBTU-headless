import asyncio
import aiohttp
import os
from urllib.parse import urljoin, urlparse, parse_qs, urlencode
import re
from datetime import datetime
import json
import csv
from pathlib import Path
import hashlib
import time
from collections import defaultdict
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
BASE_URL = "https://kbtu.edu.kz/en/"
MAX_DEPTH = 5
MAX_PAGES = 1200
MAX_PAGINATION_PAGES = 10
OUTPUT_DIR = "/data/site_audit"
IGNORE_ROBOTS = True

# Create output directory
Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

# URL patterns
ALLOW_PATTERNS = [
    r"^/en/?$",
    r"^/en/about",
    r"^/en/academics",
    r"^/en/admissions",
    r"^/en/research",
    r"^/en/news",
    r"^/en/events",
    r"^/en/faculties",
    r"^/en/schools",
    r"^/en/departments",
    r"^/en/contacts",
    r"^/en/career",
    r"^/en/centers",
    r"^/en/library"
]

DENY_PATTERNS = [
    r"^/(ru|kk)(/|$)",
    r"lang=(?!en)",
    r"/login",
    r"/admin",
    r"/user",
    r"/basket",
    r"/cart",
    r"^/en/search",
    r"\?s=",
    r"\?search=",
    r"\.(pdf|docx?|xlsx?|pptx?|zip|rar|7z|mp4|avi|webm|mov)$"
]

# Tracking parameters to remove
TRACKING_PARAMS = ["utm_*", "fbclid", "gclid", "mc_cid", "mc_eid"]

# Stable parameters to keep
STABLE_PARAMS = ["page", "q", "category", "tag", "date"]

# Initialize data storage
visited_urls = set()
url_content_hashes = {}
redirect_map = []
error_log = []
api_endpoints = []
integrations = []
forms_data = []
content_data = []
structured_data_entries = []
seo_data = []
media_data = []
url_inventory = []
hreflang_map = []
sitemaps_found = []

# Rate limiting
CONCURRENT_REQUESTS = 3
REQUEST_DELAY = 0.5  # seconds

# Semaphore for limiting concurrent requests
semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)

def normalize_url(url, base_url=BASE_URL):
    """Normalize URL by removing tracking parameters and ensuring consistent format"""
    parsed = urlparse(url)
    
    # Remove tracking parameters
    query_params = parse_qs(parsed.query)
    filtered_params = {}
    
    for key, value in query_params.items():
        # Check if parameter is a tracking parameter
        is_tracking = any(re.match(param.replace("*", ".*"), key) for param in TRACKING_PARAMS)
        if not is_tracking:
            # Keep stable parameters or those with limited values
            if key in STABLE_PARAMS or len(set(value)) <= 5:
                filtered_params[key] = value
    
    # Reconstruct query string
    normalized_query = urlencode(filtered_params, doseq=True)
    
    # Reconstruct URL
    normalized = parsed._replace(query=normalized_query, fragment="")
    return normalized.geturl()

def is_allowed_url(url):
    """Check if URL matches allowed patterns and doesn't match deny patterns"""
    path = urlparse(url).path
    
    # Check if it's an English URL
    if not path.startswith("/en/"):
        return False
    
    # Check deny patterns first
    for pattern in DENY_PATTERNS:
        if re.match(pattern, url) or re.match(pattern, path):
            return False
    
    # Check allow patterns
    for pattern in ALLOW_PATTERNS:
        if re.match(pattern, path):
            return True
    
    return False

def get_url_type(url, content=""):
    """Determine the type of page based on URL and content"""
    path = urlparse(url).path
    
    if path == "/en/" or path == "/en":
        return "home"
    elif "/news" in path:
        return "listing"
    elif "/events" in path:
        return "event"
    elif "/faculty" in path or "/faculties" in path:
        return "faculty"
    elif "/department" in path or "/departments" in path:
        return "department"
    elif "/academics" in path:
        return "page"
    elif "/about" in path:
        return "page"
    elif "/admissions" in path:
        return "page"
    elif "/research" in path:
        return "page"
    elif "/contacts" in path:
        return "contact"
    elif "/career" in path:
        return "page"
    elif "/centers" in path:
        return "page"
    elif "/library" in path:
        return "page"
    else:
        # Default to article if it has article-like content
        if "<article" in content or '"@type":"Article"' in content:
            return "article"
        return "page"

def extract_structured_data(html_content, url):
    """Extract JSON-LD structured data from HTML content"""
    import re
    json_ld_scripts = re.findall(r'<script[^>]*type=[\'"]application/ld\+json[\'"][^>]*>(.*?)</script>', html_content, re.DOTALL)
    
    structured_data = []
    for script in json_ld_scripts:
        try:
            data = json.loads(script)
            structured_data.append({
                "url": url,
                "schema": data
            })
        except json.JSONDecodeError:
            continue
    
    return structured_data

def extract_seo_data(html_content, url):
    """Extract SEO-related data from HTML content"""
    import re
    
    # Extract title
    title_match = re.search(r'<title[^>]*>(.*?)</title>', html_content, re.DOTALL)
    title = title_match.group(1).strip() if title_match else ""
    
    # Extract meta description
    desc_match = re.search(r'<meta[^>]*name=[\'"]description[\'"][^>]*content=[\'"]([^\'"]*)[\'"]', html_content)
    meta_description = desc_match.group(1) if desc_match else ""
    
    # Extract robots meta
    robots_match = re.search(r'<meta[^>]*name=[\'"]robots[\'"][^>]*content=[\'"]([^\'"]*)[\'"]', html_content)
    robots_meta = robots_match.group(1) if robots_match else ""
    
    # Extract Open Graph data
    og_title_match = re.search(r'<meta[^>]*property=[\'"]og:title[\'"][^>]*content=[\'"]([^\'"]*)[\'"]', html_content)
    og_title = og_title_match.group(1) if og_title_match else ""
    
    og_desc_match = re.search(r'<meta[^>]*property=[\'"]og:description[\'"][^>]*content=[\'"]([^\'"]*)[\'"]', html_content)
    og_description = og_desc_match.group(1) if og_desc_match else ""
    
    og_image_match = re.search(r'<meta[^>]*property=[\'"]og:image[\'"][^>]*content=[\'"]([^\'"]*)[\'"]', html_content)
    og_image = og_image_match.group(1) if og_image_match else ""
    
    # Extract Twitter card data
    twitter_card_match = re.search(r'<meta[^>]*name=[\'"]twitter:card[\'"][^>]*content=[\'"]([^\'"]*)[\'"]', html_content)
    twitter_card = twitter_card_match.group(1) if twitter_card_match else ""
    
    # Extract JSON-LD types
    json_ld_scripts = re.findall(r'<script[^>]*type=[\'"]application/ld\+json[\'"][^>]*>(.*?)</script>', html_content, re.DOTALL)
    jsonld_types = []
    for script in json_ld_scripts:
        try:
            data = json.loads(script)
            if "@type" in data:
                jsonld_types.append(data["@type"])
            elif isinstance(data, list):
                for item in data:
                    if "@type" in item:
                        jsonld_types.append(item["@type"])
        except json.JSONDecodeError:
            continue
    
    return {
        "url": url,
        "title": title,
        "meta_description": meta_description,
        "robots_meta": robots_meta,
        "og:title": og_title,
        "og:description": og_description,
        "og:image": og_image,
        "twitter:card": twitter_card,
        "jsonld_types": jsonld_types
    }

def extract_content_data(html_content, url):
    """Extract content data from HTML"""
    import re
    from bs4 import BeautifulSoup
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
    except:
        # Fallback if BeautifulSoup fails
        soup = None
    
    # Extract H1
    h1 = ""
    if soup:
        h1_tag = soup.find('h1')
        if h1_tag:
            h1 = h1_tag.get_text(strip=True)
    else:
        h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', html_content, re.DOTALL)
        h1 = h1_match.group(1).strip() if h1_match else ""
    
    # Extract breadcrumbs
    breadcrumbs = []
    if soup:
        breadcrumb_nav = soup.find('nav', class_=re.compile(r'.*breadcrumb.*'))
        if breadcrumb_nav:
            breadcrumb_links = breadcrumb_nav.find_all('a')
            breadcrumbs = [link.get_text(strip=True) for link in breadcrumb_links]
    
    # Extract publish date (simplified)
    date_published = None
    if soup:
        # Look for common date patterns
        time_tag = soup.find('time')
        if time_tag and time_tag.get('datetime'):
            date_published = time_tag.get('datetime')
    
    # Extract tags (simplified)
    tags = []
    
    # Extract summary (first paragraph)
    summary = ""
    if soup:
        first_p = soup.find('p')
        if first_p:
            summary = first_p.get_text(strip=True)[:200]  # First 200 chars
    
    # Extract body blocks
    body_blocks = []
    if soup:
        # Extract paragraphs
        paragraphs = soup.find_all('p')
        for p in paragraphs:
            text = p.get_text(strip=True)
            if text:
                body_blocks.append({
                    "type": "paragraph",
                    "text": text
                })
        
        # Extract headings
        for i in range(1, 7):
            headings = soup.find_all(f'h{i}')
            for heading in headings:
                text = heading.get_text(strip=True)
                if text:
                    body_blocks.append({
                        "type": "heading",
                        "level": i,
                        "text": text
                    })
        
        # Extract images
        images = soup.find_all('img')
        for img in images:
            src = img.get('src', '')
            alt = img.get('alt', '')
            if src:
                body_blocks.append({
                    "type": "image",
                    "src": src,
                    "alt": alt
                })
        
        # Extract lists
        lists = soup.find_all(['ul', 'ol'])
        for lst in lists:
            items = [li.get_text(strip=True) for li in lst.find_all('li')]
            if items:
                body_blocks.append({
                    "type": "list",
                    "ordered": lst.name == 'ol',
                    "items": items
                })
    
    return {
        "url": url,
        "h1": h1,
        "breadcrumbs": breadcrumbs,
        "date_published": date_published,
        "author": None,  # Would need more specific parsing
        "tags": tags,
        "summary": summary,
        "body_blocks": body_blocks
    }

def extract_media_data(html_content, url):
    """Extract media data from HTML"""
    import re
    from bs4 import BeautifulSoup
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
    except:
        soup = None
    
    media_entries = []
    
    # Extract images
    if soup:
        images = soup.find_all('img')
        for img in images:
            src = img.get('src', '')
            if src:
                media_entries.append({
                    "url": src,
                    "page_url": url,
                    "alt": img.get('alt', ''),
                    "width": img.get('width', ''),
                    "height": img.get('height', ''),
                    "type": "image",
                    "filesize": "",  # Would need HEAD request to determine
                    "loading_attr": img.get('loading', ''),
                    "srcset_count": len(img.get('srcset', '').split(',')) if img.get('srcset') else 0
                })
        
        # Extract videos
        videos = soup.find_all('video')
        for video in videos:
            src = video.get('src', '')
            if src:
                media_entries.append({
                    "url": src,
                    "page_url": url,
                    "alt": "",
                    "width": video.get('width', ''),
                    "height": video.get('height', ''),
                    "type": "video",
                    "filesize": "",
                    "loading_attr": "",
                    "srcset_count": 0
                })
            
            # Check sources within video
            sources = video.find_all('source')
            for source in sources:
                src = source.get('src', '')
                if src:
                    media_entries.append({
                        "url": src,
                        "page_url": url,
                        "alt": "",
                        "width": "",
                        "height": "",
                        "type": "video",
                        "filesize": "",
                        "loading_attr": "",
                        "srcset_count": 0
                    })
        
        # Extract audio
        audios = soup.find_all('audio')
        for audio in audios:
            src = audio.get('src', '')
            if src:
                media_entries.append({
                    "url": src,
                    "page_url": url,
                    "alt": "",
                    "width": "",
                    "height": "",
                    "type": "audio",
                    "filesize": "",
                    "loading_attr": "",
                    "srcset_count": 0
                })
            
            # Check sources within audio
            sources = audio.find_all('source')
            for source in sources:
                src = source.get('src', '')
                if src:
                    media_entries.append({
                        "url": src,
                        "page_url": url,
                        "alt": "",
                        "width": "",
                        "height": "",
                        "type": "audio",
                        "filesize": "",
                        "loading_attr": "",
                        "srcset_count": 0
                    })
    
    return media_entries

def extract_forms_data(html_content, url):
    """Extract form data from HTML"""
    import re
    from bs4 import BeautifulSoup
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
    except:
        return []
    
    forms = soup.find_all('form')
    forms_entries = []
    
    for form in forms:
        form_name = form.get('name', '')
        method = form.get('method', 'GET').upper()
        action = form.get('action', '')
        
        # Resolve relative action URL
        if action:
            action = urljoin(url, action)
        
        # Check for reCAPTCHA
        has_recaptcha = bool(form.find_all('div', class_=re.compile(r'.*g-recaptcha.*'))) or \
                        bool(form.find_all('input', {'name': 'g-recaptcha-response'}))
        
        # Extract fields
        fields = []
        field_elements = form.find_all(['input', 'select', 'textarea'])
        
        for field in field_elements:
            field_data = {
                "name": field.get('name', ''),
                "type": field.get('type', 'text'),
                "required": field.get('required') is not None
            }
            
            # Add additional attributes based on field type
            if field.name == 'input':
                if field.get('type') == 'text':
                    minlength = field.get('minlength')
                    if minlength:
                        field_data['minlength'] = minlength
                elif field.get('type') == 'email':
                    # Email validation is implicit
                    pass
            elif field.name == 'textarea':
                minlength = field.get('minlength')
                if minlength:
                    field_data['minlength'] = minlength
            
            fields.append(field_data)
        
        # Check for honeypot fields (hidden fields that shouldn't be filled)
        honeypot_field = None
        hidden_fields = form.find_all('input', {'type': 'hidden'})
        for field in hidden_fields:
            name = field.get('name', '').lower()
            # Common honeypot field names
            if any(keyword in name for keyword in ['website', 'url', 'honeypot', 'bot']):
                honeypot_field = name
                break
        
        forms_entries.append({
            "page_url": url,
            "form_name": form_name,
            "action": f"{method} {action}" if action else method,
            "method": method,
            "has_recaptcha": has_recaptcha,
            "fields_count": len(fields),
            "success_text": "",  # Would need more complex parsing
            "error_text": "",    # Would need more complex parsing
            "fields": fields,
            "antispam": {
                "recaptcha": has_recaptcha,
                "honeypot_field": honeypot_field
            },
            "validation": {
                "client": ["required"] if any(f.get('required') for f in fields) else [],
                "server": []  # Would identify from action URL or JS
            }
        })
    
    return forms_entries

def extract_integrations(html_content, url):
    """Extract third-party integrations from HTML"""
    import re
    
    integrations = []
    
    # Google Analytics 4 / Google Tag Manager
    ga4_matches = re.findall(r'gtag\([^)]*\'(G-[A-Z0-9]+)\'', html_content)
    for match in ga4_matches:
        integrations.append({
            "page_url": url,
            "tool": "GA4",
            "id": match,
            "loaded_from": "https://www.googletagmanager.com/gtag/js"
        })
    
    gtm_matches = re.findall(r'GTM-[A-Z0-9]+', html_content)
    for match in gtm_matches:
        integrations.append({
            "page_url": url,
            "tool": "GTM",
            "id": match,
            "loaded_from": "https://www.googletagmanager.com"
        })
    
    # Meta Pixel
    pixel_matches = re.findall(r'fbq\([^)]*\'track\'[^)]*\'[A-Z0-9]+\'', html_content)
    if pixel_matches:
        integrations.append({
            "page_url": url,
            "tool": "Meta Pixel",
            "id": "detected",
            "loaded_from": "https://connect.facebook.net"
        })
    
    # Hotjar
    hotjar_matches = re.findall(r'hj\([^)]*\'[0-9]+\'', html_content)
    if hotjar_matches:
        integrations.append({
            "page_url": url,
            "tool": "Hotjar",
            "id": "detected",
            "loaded_from": "https://static.hotjar.com"
        })
    
    # Intercom
    if 'intercom' in html_content.lower():
        integrations.append({
            "page_url": url,
            "tool": "Intercom",
            "id": "detected",
            "loaded_from": "https://widget.intercom.io"
        })
    
    # Google Maps
    if 'maps.googleapis.com' in html_content:
        integrations.append({
            "page_url": url,
            "tool": "Google Maps",
            "id": "detected",
            "loaded_from": "https://maps.googleapis.com"
        })
    
    # reCAPTCHA
    if 'recaptcha' in html_content.lower():
        integrations.append({
            "page_url": url,
            "tool": "reCAPTCHA",
            "id": "detected",
            "loaded_from": "https://www.google.com/recaptcha"
        })
    
    return integrations

def extract_api_endpoints(html_content, url):
    """Extract API endpoints from HTML (from JS code)"""
    import re
    
    api_endpoints = []
    
    # Simple pattern for API endpoints in JS
    # This is a basic implementation - in a real crawler, you'd want to parse JS properly
    api_patterns = [
        r'https?://[^\'"\s]*api[^\'"\s]*',
        r'https?://[^\'"\s]*\.json',
        r'fetch\([\'"]([^\'"]*)[\'"]\)',
        r'axios\.get\([\'"]([^\'"]*)[\'"]\)'
    ]
    
    for pattern in api_patterns:
        matches = re.findall(pattern, html_content)
        for match in matches:
            # If it's just the URL (not the full JS code)
            if match:
                endpoint_url = match if 'http' in match else urljoin(url, match)
                api_endpoints.append({
                    "page_url": url,
                    "method": "GET",  # Default assumption
                    "url": endpoint_url,
                    "status": "",  # Will be filled during actual request
                    "content_type": ""  # Will be filled during actual request
                })
    
    return api_endpoints

async def fetch_page(session, url, depth=0, discovered_from=""):
    """Fetch a page and extract data"""
    global visited_urls, url_content_hashes, redirect_map, error_log
    
    # Normalize URL
    normalized_url = normalize_url(url)
    
    # Check if already visited
    if normalized_url in visited_urls:
        return []
    
    # Check if within allowed paths
    if not is_allowed_url(normalized_url):
        logger.info(f"Skipping non-English URL: {normalized_url}")
        error_log.append({
            "url": normalized_url,
            "status": "skipped",
            "referrer": discovered_from,
            "notes": "skipped_non_en"
        })
        return []
    
    # Limit to max pages
    if len(visited_urls) >= MAX_PAGES:
        return []
    
    visited_urls.add(normalized_url)
    
    try:
        async with semaphore:  # Limit concurrent requests
            # Add delay to respect rate limits
            await asyncio.sleep(REQUEST_DELAY)
            
            # Make request
            async with session.get(normalized_url, timeout=aiohttp.ClientTimeout(total=45)) as response:
                status = response.status
                content_type = response.headers.get('content-type', '')
                
                # Handle redirects
                if status in [301, 302, 303, 307, 308]:
                    location = response.headers.get('location', '')
                    if location:
                        redirect_map.append({
                            "from": normalized_url,
                            "to": location,
                            "http_status": status,
                            "via": "header"
                        })
                        # Follow redirect if within depth limit
                        if depth < MAX_DEPTH:
                            redirect_url = urljoin(normalized_url, location)
                            return await fetch_page(session, redirect_url, depth+1, discovered_from=normalized_url)
                
                # Handle errors
                if status >= 400:
                    error_log.append({
                        "url": normalized_url,
                        "status": status,
                        "referrer": discovered_from,
                        "notes": f"HTTP {status}"
                    })
                    return []
                
                # Only process HTML content
                if 'text/html' not in content_type:
                    return []
                
                # Read content
                html_content = await response.text()
                
                # Calculate content hash to detect duplicates
                content_hash = hashlib.md5(html_content.encode('utf-8')).hexdigest()
                if content_hash in url_content_hashes:
                    # This is a duplicate page
                    url_inventory.append({
                        "url": normalized_url,
                        "type": "duplicate",
                        "template": "",
                        "depth": depth,
                        "status": status,
                        "redirected_from": "",
                        "canonical": "",
                        "hreflang": "",
                        "paginated": False,
                        "discovered_from": discovered_from,
                        "duplicate_of": url_content_hashes[content_hash]
                    })
                    return []
                
                url_content_hashes[content_hash] = normalized_url
                
                # Extract data
                await extract_page_data(session, normalized_url, html_content, status, depth, discovered_from)
                
                # Find new URLs to crawl
                new_urls = await find_links(session, normalized_url, html_content, depth)
                
                return new_urls
                
    except asyncio.TimeoutError:
        error_log.append({
            "url": normalized_url,
            "status": "timeout",
            "referrer": discovered_from,
            "notes": "Request timeout after 45 seconds"
        })
        return []
    except Exception as e:
        error_log.append({
            "url": normalized_url,
            "status": "error",
            "referrer": discovered_from,
            "notes": str(e)
        })
        return []

async def extract_page_data(session, url, html_content, status, depth, discovered_from):
    """Extract all data from a page"""
    # Determine page type
    page_type = get_url_type(url, html_content)
    
    # Extract structured data
    structured_data = extract_structured_data(html_content, url)
    structured_data_entries.extend(structured_data)
    
    # Extract SEO data
    seo_info = extract_seo_data(html_content, url)
    seo_data.append(seo_info)
    
    # Extract content data
    content_info = extract_content_data(html_content, url)
    content_data.append(content_info)
    
    # Extract media data
    media_info = extract_media_data(html_content, url)
    media_data.extend(media_info)
    
    # Extract forms data
    forms_info = extract_forms_data(html_content, url)
    forms_data.extend(forms_info)
    
    # Extract integrations
    integration_info = extract_integrations(html_content, url)
    integrations.extend(integration_info)
    
    # Extract API endpoints (from JS)
    api_info = extract_api_endpoints(html_content, url)
    api_endpoints.extend(api_info)
    
    # Try to identify if page is paginated
    is_paginated = "?page=" in url or "/page/" in url
    
    # Add to URL inventory
    url_inventory.append({
        "url": url,
        "type": page_type,
        "template": "",  # Would need DOM analysis to determine
        "depth": depth,
        "status": status,
        "redirected_from": "",  # Would be set for redirects
        "canonical": "",  # Would extract from link[rel="canonical"]
        "hreflang": "",  # Would extract from link[rel="alternate"][hreflang]
        "paginated": is_paginated,
        "discovered_from": discovered_from
    })

async def find_links(session, base_url, html_content, current_depth):
    """Find all links on a page that should be crawled"""
    import re
    from bs4 import BeautifulSoup
    
    if current_depth >= MAX_DEPTH:
        return []
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
    except:
        # Fallback to regex
        soup = None
    
    links = []
    
    if soup:
        # Find all <a> tags
        anchor_tags = soup.find_all('a', href=True)
        for tag in anchor_tags:
            href = tag['href']
            absolute_url = urljoin(base_url, href)
            links.append(absolute_url)
        
        # Handle pagination - look for "Load more" buttons or pagination links
        pagination_links = []
        
        # Check for common pagination patterns
        page_links = soup.find_all('a', href=re.compile(r'(\?page=|/page/)\d+'))
        for link in page_links:
            href = link['href']
            absolute_url = urljoin(base_url, href)
            pagination_links.append(absolute_url)
        
        # Limit pagination links
        links.extend(pagination_links[:MAX_PAGINATION_PAGES])
    else:
        # Fallback regex approach
        href_matches = re.findall(r'href=[\'"]([^\'"]*)[\'"]', html_content)
        for href in href_matches:
            absolute_url = urljoin(base_url, href)
            links.append(absolute_url)
    
    # Filter and normalize links
    valid_links = []
    for link in links:
        normalized = normalize_url(link)
        if is_allowed_url(normalized) and normalized not in visited_urls:
            valid_links.append(normalized)
    
    return valid_links

async def crawl_website():
    """Main crawling function"""
    # Initialize aiohttp session
    async with aiohttp.ClientSession() as session:
        # Start with base URL
        urls_to_crawl = [BASE_URL]
        current_depth = 0
        
        while urls_to_crawl and len(visited_urls) < MAX_PAGES and current_depth < MAX_DEPTH:
            # Process URLs at current depth
            next_urls = []
            
            # Limit concurrent tasks
            tasks = [fetch_page(session, url, current_depth) for url in urls_to_crawl[:10]]  # Process 10 at a time
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Collect new URLs
            for result in results:
                if isinstance(result, list):
                    next_urls.extend(result)
                elif isinstance(result, Exception):
                    logger.error(f"Error crawling: {result}")
            
            # Prepare for next depth
            urls_to_crawl = list(set(next_urls))  # Remove duplicates
            current_depth += 1
            
            logger.info(f"Depth {current_depth}: {len(urls_to_crawl)} URLs to crawl, {len(visited_urls)} visited so far")
        
        # Save all data
        save_data()

def save_data():
    """Save all collected data to files"""
    # Save URL inventory
    with open(os.path.join(OUTPUT_DIR, "urls.csv"), "w", newline="", encoding="utf-8") as f:
        fieldnames = ["url", "type", "template", "depth", "status", "redirected_from", 
                     "canonical", "hreflang", "paginated", "discovered_from"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(url_inventory)
    
    # Save SEO data
    with open(os.path.join(OUTPUT_DIR, "seo.csv"), "w", newline="", encoding="utf-8") as f:
        fieldnames = ["url", "title", "meta_description", "robots_meta", "og:title", 
                     "og:description", "og:image", "twitter:card", "jsonld_types"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(seo_data)
    
    # Save structured data
    with open(os.path.join(OUTPUT_DIR, "structured_data.jsonl"), "w", encoding="utf-8") as f:
        for item in structured_data_entries:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    
    # Save content data
    with open(os.path.join(OUTPUT_DIR, "content.jsonl"), "w", encoding="utf-8") as f:
        for item in content_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    
    # Save media data
    with open(os.path.join(OUTPUT_DIR, "media.csv"), "w", newline="", encoding="utf-8") as f:
        fieldnames = ["url", "page_url", "alt", "width", "height", "type", "filesize", 
                     "loading_attr", "srcset_count"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(media_data)
    
    # Save forms data
    with open(os.path.join(OUTPUT_DIR, "forms.csv"), "w", newline="", encoding="utf-8") as f:
        fieldnames = ["page_url", "form_name", "method", "action", "has_recaptcha", 
                     "fields_count", "success_text", "error_text"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        # Extract CSV-compatible data from forms_data
        csv_forms = []
        for form in forms_data:
            csv_form = {
                "page_url": form["page_url"],
                "form_name": form["form_name"],
                "method": form["method"],
                "action": form["action"],
                "has_recaptcha": form["has_recaptcha"],
                "fields_count": form["fields_count"],
                "success_text": form["success_text"],
                "error_text": form["error_text"]
            }
            csv_forms.append(csv_form)
        writer.writerows(csv_forms)
    
    with open(os.path.join(OUTPUT_DIR, "forms.jsonl"), "w", encoding="utf-8") as f:
        for item in forms_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    
    # Save integrations
    with open(os.path.join(OUTPUT_DIR, "integrations.jsonl"), "w", encoding="utf-8") as f:
        for item in integrations:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    
    # Save API endpoints
    with open(os.path.join(OUTPUT_DIR, "api_endpoints.jsonl"), "w", encoding="utf-8") as f:
        for item in api_endpoints:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    
    # Save redirects
    with open(os.path.join(OUTPUT_DIR, "redirects.csv"), "w", newline="", encoding="utf-8") as f:
        fieldnames = ["from", "to", "http_status", "via"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(redirect_map)
    
    # Save errors
    with open(os.path.join(OUTPUT_DIR, "errors.csv"), "w", newline="", encoding="utf-8") as f:
        fieldnames = ["url", "status", "referrer", "notes"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(error_log)
    
    # Save sitemaps (empty file as placeholder)
    with open(os.path.join(OUTPUT_DIR, "sitemaps.txt"), "w", encoding="utf-8") as f:
        for sitemap in sitemaps_found:
            f.write(sitemap + "\n")
    
    # Save hreflang map (empty file as placeholder)
    with open(os.path.join(OUTPUT_DIR, "hreflang_map.jsonl"), "w", encoding="utf-8") as f:
        for item in hreflang_map:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    
    # Print summary
    page_count = len([u for u in url_inventory if u["type"] != "duplicate"])
    article_count = len([u for u in url_inventory if u["type"] == "article"])
    listing_count = len([u for u in url_inventory if u["type"] == "listing"])
    static_count = len([u for u in url_inventory if u["type"] == "page"])
    form_count = len(forms_data)
    media_count = len(media_data)
    redirect_count = len(redirect_map)
    error_count = len(error_log)
    api_count = len(api_endpoints)
    
    print(f"DONE pages={page_count} articles={article_count} listings={listing_count} "
          f"static={static_count} forms={form_count} media={media_count} "
          f"redirects={redirect_count} errors={error_count} apis={api_count}")

if __name__ == "__main__":
    # Install required packages if needed
    try:
        import aiohttp
        import bs4
    except ImportError:
        import subprocess
        import sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "aiohttp", "beautifulsoup4"])
        import aiohttp
        import bs4
    
    # Start crawling
    asyncio.run(crawl_website())