# KBTU Site Structure - Django Implementation Summary

Based on the extracted data from the KBTU website, here's a suggested Django implementation structure:

## Apps Overview

1. **faculties** - Manages school/faculty information
2. **departments** - Handles departmental structures within faculties
3. **programs** - Manages academic programs offered
4. **content** - Handles pages, news, and general content
5. **topics** - Manages academic topics and areas of study
6. **core** - Shared models and utilities

## Models and Fields

### faculties app

- **Faculty**
  - `slug` (CharField, unique)
  - `source_url` (URLField)
  - `created_at`, `updated_at` (DateTimeFields)

### departments app

- **Department**
  - `faculty` (ForeignKey to Faculty)
  - `slug` (CharField, unique)
  - `source_url` (URLField)
  - `created_at`, `updated_at` (DateTimeFields)

### programs app

- **Program**
  - `level` (CharField with choices: bachelor, master, phd, other)
  - `faculty` (ForeignKey to Faculty, optional)
  - `department` (ForeignKey to Department, optional)
  - `slug` (CharField, unique)
  - `source_url` (URLField)
  - `created_at`, `updated_at` (DateTimeFields)

### content app

- **Page**
  - `kind` (CharField with choices: generic, admissions, about, etc.)
  - `slug` (CharField, unique)
  - `source_url` (URLField)
  - `created_at`, `updated_at` (DateTimeFields)

### topics app

- **Topic**
  - `slug` (CharField, unique)
  - `source_url` (URLField)
  - `created_at`, `updated_at` (DateTimeFields)

### core app

- **TimeStampedModel** (abstract base model)
  - `created_at`, `updated_at` (DateTimeFields)
- **TranslatedFields** (abstract base model for translation support)
  - `translations` (JSONField for storing multilingual content)

## Relationships

1. **Faculty** тЖТ (OneToMany) тЖТ **Program** (foreign key: `faculty`)
2. **Faculty** тЖТ (OneToMany) тЖТ **Department** (foreign key: `faculty`)
3. **Department** тЖТ (OneToMany) тЖТ **Program** (foreign key: `department`)
4. **Program** тЖТ (ManyToMany) тЖТ **Topic** (through intermediate model)
5. **Page** тЖТ (ManyToMany) тЖТ **Topic** (through intermediate model)

Additional relationships could be added based on extended crawling:

- **Program** тЖТ (ManyToMany) тЖТ **Page** (for program detail pages)
- **Faculty** тЖТ (ManyToMany) тЖТ **Topic** (for faculty research areas)

## Internationalization Strategy

All models requiring multilingual support will implement translations through:

1. **JSON Fields Approach**: Using a `translations` JSONField in each model that needs internationalization

   ```python
   translations = models.JSONField(default=dict)
   ```

   Structure:

   ```json
   {
     "en": { "title": "Computer Science", "description": "..." },
     "ru": {
       "title": "╨Ъ╨╛╨╝╨┐╤М╤О╤В╨╡╤А╨╜╤Л╨╡ ╨╜╨░╤Г╨║╨╕",
       "description": "..."
     },
     "kk": {
       "title": "╨Х╤Б╨╡╨┐╤В╨╡╤Г ╤В╨╡╤Е╨╜╨╕╨║╨░╤Б╤Л",
       "description": "..."
     }
   }
   ```

2. **Helper Methods**:

   ```python
   def get_translation(self, language_code):
       return self.translations.get(language_code, {})

   def get_title(self, language_code):
       return self.get_translation(language_code).get('title', '')
   ```

This approach balances simplicity with performance, avoiding complex database joins while maintaining flexibility.

## Shared Resource Notes

1. **Abstract Base Models**:

   - `TimeStampedModel` in core app for consistent creation/update tracking
   - `TranslatedFields` in core app for consistent internationalization implementation

2. **Common Fields**:

   - All main models will have `source_url` for tracking original sources
   - All main models will have `slug` fields for clean URLs
   - All main models will inherit from `TimeStampedModel`

3. **Intermediary Models**:

   - For ManyToMany relationships (e.g., Program-Topic), intermediary models can store additional relationship data like `source_url` and timestamps

4. **Utility Functions**:
   - Slug generation from titles
   - Language fallback mechanisms for translations
   - URL validation and normalization functions

## Diagram-Style Interaction Map

```
faculties
    тФВ
    тФЬтФАтФА departments
    тФВ     тФВ
    тФВ     тФФтФАтФА programs
    тФВ
    тФФтФАтФА programs

topics тЖРтЖТ programs (M2M)
topics тЖРтЖТ pages (M2M)

content (pages)
```

This structure provides a solid foundation for a Django implementation that captures the key entities and relationships present on the KBTU website. The modular approach allows for easy extension as more parts of the site are crawled, and the translation strategy supports the multilingual nature of the institution.
