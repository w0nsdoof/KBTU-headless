# Django Implementation Blueprint - KBTU Headless Site (Enhanced)

## 1. Project Structure & Conventions

### Repository Layout
```
kbtu-cms/
├── apps/
│   ├── content/
│   ├── media/
│   ├── seo/
│   ├── search/
│   ├── accounts/
│   ├── api/
│   ├── departments/
│   └── integration/
├── config/
│   ├── settings/
│   │   ├── base.py
│   │   ├── local.py
│   │   ├── staging.py
│   │   └── production.py
│   ├── urls.py
│   └── wsgi.py
├── staticfiles/
├── mediafiles/
├── templates/
├── requirements/
│   ├── base.txt
│   ├── local.txt
│   ├── staging.txt
│   └── production.txt
├── manage.py
└── README.md
```

### Environments & Settings Strategy
- **Local**: Development environment with debug settings
- **Staging**: Pre-production environment mirroring production
- **Production**: Live environment with optimized settings

Settings strategy uses `base.py` with environment-specific overrides.

### Technology Stack
- **Python**: 3.11+
- **Django**: 4.2 LTS
- **Django REST Framework**: 3.14+
- **Key Libraries**:
  - `drf-spectacular` for API documentation
  - `django-environ` for configuration
  - `django-redis` for caching
  - `whitenoise` for static files
  - `django-storages` for media storage
  - `celery` for background tasks
  - `django-ckeditor` for WYSIWYG editing
  - `django-guardian` for object-level permissions

## 2. Apps & Responsibilities

### Core Apps

| App | Purpose | Key Models |
|-----|---------|------------|
| `content` | Manages core content types and relationships | `StaticPage`, `Article`, `Event`, `Program`, `FacultyProfile` |
| `media` | Handles asset storage and image processing | `MediaAsset`, `ImageRendition` |
| `seo` | Manages SEO metadata and structured data | `SEOMetadata`, `Sitemap`, `StructuredData` |
| `search` | Implements search functionality | `SearchIndex`, `SearchQuery` |
| `accounts` | User management and authentication | `User`, `UserRole` |
| `api` | Exposes RESTful endpoints | `APIVersion`, `ThrottleConfig` |
| `departments` | Department-specific pages with RBAC | `DepartmentPage`, `DepartmentRole`, `DepartmentPermission` |
| `integration` | Third-party service integrations | `AnalyticsConfig`, `ChatWidget` |

### Inter-App Dependencies
```
accounts ←── departments
    ↓           ↓
content → media
    ↓       ↓
   seo ←───┘
    ↓
api → search
    ↓
integration
```

Anti-coupling rules:
- `content` cannot import from `api`, `search`, or `integration`
- `media` is a leaf node with no dependencies
- `seo` can import from `content` but not vice versa
- `departments` can import from `content` and `accounts`

## 3. Data Model Overview

### Key Entities & Relationships
```
FacultyProfile 1─┐                 ScientificEmployeeProfile
                 ├─ DepartmentPage 1─┐
ProgramPage 1─┘  │                  │
                 ├─ StaticPage ∞    │
Article ∞─→ FacultyProfile (author)│
                 │                  │
Event ∞──────────┘                  │
                                    │
StaticPage ∞ ──────────────────────┘
```

### Employee Profile Types
- **FacultyProfile**: Academic faculty members with teaching responsibilities
- **ScientificEmployeeProfile**: Research staff and scientific personnel
- **EducationalEmployeeProfile**: Staff focused on educational support

### Department Pages with RBAC
- Custom department pages with WYSIWYG editing
- Role-based access control for editing permissions
- Department-specific roles: Head, Editor, Contributor

### Slugs & i18n Strategy
- Slugs: Unique per content type, auto-generated from title
- i18n: Language code prefix in URLs (e.g., `/en/about/`)
- Publication workflow: Draft → Published → Scheduled
- Revisions: Stored as JSON snapshots with timestamp and user

## 4. API Layer (DRF)

### Versioning & Routing
```
/api/v1/
├── articles/
│   ├── ?page=1&limit=20
│   ├── ?search=keyword
│   └── {slug}/
├── events/
├── pages/
├── faculty/
├── scientific_staff/
├── educational_staff/
├── departments/
├── programs/
└── search/?q=keyword
```

### Example Endpoint
```python
# apps/api/views.py
class FacultyViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = FacultyProfile.objects.all()
    serializer_class = FacultySerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['first_name', 'last_name', 'position', 'bio']
    ordering_fields = ['last_name', 'position']
    ordering = ['last_name']

class DepartmentPageViewSet(viewsets.ModelViewSet):
    queryset = DepartmentPage.objects.all()
    serializer_class = DepartmentPageSerializer
    permission_classes = [DepartmentPagePermission]
    
    def get_queryset(self):
        # Filter based on user's department permissions
        if self.request.user.is_authenticated:
            return DepartmentPage.objects.filter(
                department__in=get_user_departments(self.request.user)
            )
        return DepartmentPage.objects.none()
```

### Authentication & Security
- Public read-only endpoints
- JWT authentication for CMS operations
- Rate throttling: 1000 requests/hour per IP
- Caching headers: ETag, Last-Modified
- Object-level permissions for department pages

## 5. SEO & Sitemaps

### Metadata Sources
- Canonical URLs: Stored as model fields with fallback to self
- Hreflang: Computed based on available translations
- Meta tags: Stored in `SEOMetadata` model linked to content

### Structured Data
JSON-LD generation for:
- Article (news)
- Event
- Organization
- BreadcrumbList
- Person (for employee profiles)
- Department (for department pages)

### Sitemaps
- Sitemap index at `/sitemap.xml`
- Per-type sitemaps:
  - `/sitemap-articles.xml`
  - `/sitemap-events.xml`
  - `/sitemap-pages.xml`
  - `/sitemap-faculty.xml`
  - `/sitemap-scientific-staff.xml`
  - `/sitemap-departments.xml`
- robots.txt with sitemap reference

## 6. Media & File Storage

### Storage Backends
- Local development: Django's default file storage
- Production: AWS S3/GCS via `django-storages`

### Image Pipeline
- Automatic variants: thumbnail, small, medium, large
- Modern formats: WebP/AVIF with fallback to JPEG/PNG
- Cache invalidation on source image update

## 7. Search Strategy

### MVP Implementation
PostgreSQL full-text search with trigram similarity

### Indexing
- Triggers: `post_save` signals for content models
- Manual: Management command for bulk reindexing

### Relevance Tuning
Weighted ranking based on:
- Title matches (highest weight)
- Summary matches (medium weight)
- Content matches (lower weight)
- Publish date (recency boost)

## 8. Caching & Performance

### Django Cache
- Redis backend for session and object caching
- Per-view caching for API endpoints
- Per-object caching for expensive queries

### Cache Keys & Invalidation
- Keys: `content_type:pk:language`
- Invalidation: On content publish/unpublish

### Static Assets
- CDN delivery via whitenoise
- Long-lived cache headers with fingerprinted filenames

## 9. Security & Compliance

### Core Protections
- HTTPS enforcement
- Strict CORS policy
- CSRF protection for admin
- Rate limiting per IP

### Admin Hardening
- Two-factor authentication
- Audit logs for all content changes
- Role-based access control
- Object-level permissions for department pages

### PII Handling
- Faculty contact info: Access-controlled fields
- GDPR compliance: Data export/deletion endpoints

## 10. Testing Strategy

### Test Types
- Unit: Model and serializer validation
- Integration: API contract tests with DRF
- Smoke: End-to-end API workflows
- Permission: RBAC and department access controls

### Performance
- Baseline: P95 API response < 300ms
- Load testing: 100 concurrent users

### Fixtures
- Factory Boy for test data generation
- Staging data seeding from production anonymized data

## 11. Operations

### Migrations
- Backward-compatible changes only
- Staged deployments with rollback plans

### Management Commands
- `reindex_search`: Rebuild search index
- `rebuild_sitemap`: Regenerate sitemap files
- `import_legacy`: Migrate content from old system
- `sync_department_permissions`: Update department RBAC mappings

### Observability
- Structured logging with request IDs
- Sentry integration for error tracking
- Health checks: `/health/` endpoint

### CI/CD
- GitHub Actions workflow:
  1. Lint (black, flake8)
  2. Test (pytest)
  3. Security scan (bandit)
  4. Deploy (Docker image to registry)

## 12. Migration Plan

### URL Mapping
- Legacy to new slug mapping in redirect table
- 301 redirects for all changed URLs

### Content Import
1. Static pages (About section)
2. Faculty profiles
3. Scientific staff profiles
4. Educational staff profiles
5. Departments and programs
6. Articles (news)
7. Events

### Media Sync
- Direct transfer from legacy to new storage
- Image rendition regeneration

### Acceptance Criteria
- 1:1 content parity
- No broken links
- SEO metrics maintained or improved
- Performance targets met
- Department RBAC working correctly

## Day-1 Tasks
- [ ] Initialize Django project with enhanced app structure
- [ ] Set up environment configuration with RBAC libraries
- [ ] Implement employee profile models (Faculty, Scientific, Educational)
- [ ] Create department pages app with RBAC foundation
- [ ] Configure WYSIWYG editor (django-ckeditor)
- [ ] Set up development database and cache

## Week-1 Milestones
- [ ] Complete all employee profile models with relationships
- [ ] Implement department pages with WYSIWYG editing
- [ ] Set up RBAC for department page editing
- [ ] Create API endpoints for all employee types
- [ ] Implement department page API with permissions
- [ ] Configure WYSIWYG editing for department pages
- [ ] Set up logging and monitoring