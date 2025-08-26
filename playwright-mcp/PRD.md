# Functional Requirements Document — KBTU Headless CMS (Backend)

## 1. Overview

- **Summary:** Migrate KBTU’s monolithic Joomla site to a headless backend on Django/DRF with normalized entities (Faculties, Departments, Programs, Pages, Topics, Media), RBAC, and multilingual support. Angular will consume the API later. Focus now is backend schema, API, and content workflows

- **Business Goals & KPIs:**

  - Reduce content duplication via shared resources and normalized data
  - Empower departments to publish without developer involvement (≥10 departmental landing pages edited by non-devs).;
  - Uptime SLA ≥99.5% during academic periods; publish latency ≤5 minutes from editor action to live content.;
  - _Assumption:_ API p95 latency ≤500 ms for list endpoints.

- **Success Criteria:**
  - ≥80% content auto-migrated; remaining content addressed via manual cleanup.;
  - MVP API live with Faculties, Departments, Programs, Pages, Topics, Media; Angular can render required views.
  - RBAC enables department-scoped editing; draft→publish workflow operational.

## 2. Scope

- **In Scope:**

  - Django apps: `core`, `org` (Faculties/Departments), `programs`, `pages`, `taxonomy`, `media`, `accounts` (RBAC), `api` (routing).;
  - REST API (CRUD where applicable), filtering, pagination, JWT auth.
  - Translations stored in JSON per entity (en/ru/kk); MVP content primarily EN.;
  - WYSIWYG-like Pages via structured blocks (JSON) with limited theming; draft/publish workflow.
  - Import pipeline from extracted JSONL (faculties, departments, programs, pages, topics, edges, report). _Assumption:_ one-time batch + idempotent re-runs.

- **Out of Scope:**

  - Frontend (Angular), mobile apps; deep analytics; ElasticSearch (Phase 2); News/Events/Person profiles (Phase 2).;

## 3. Stakeholders & Users

- **Stakeholders/Roles:**

| Role                | Responsibility                      | Contact/Owner |
| ------------------- | ----------------------------------- | ------------- |
| Product BA/PM       | Requirements, scope, acceptance     | TBD           |
| Tech Lead (Backend) | Architecture, API, performance      | TBD           |
| Content/PR Team     | Page content, approvals             | TBD           |
| Department Editors  | Faculty/department content          | TBD           |
| DevOps              | CI/CD, hosting, backups, monitoring | TBD           |

- **User Personas:**

| Persona                | Goals                         | Pain Points                   | Primary Flows                 |
| ---------------------- | ----------------------------- | ----------------------------- | ----------------------------- |
| Admin                  | Configure, manage all content | Fragmented data, no audit     | Global CRUD, RBAC, workflow   |
| Content Manager        | Create/edit Pages             | Reliance on devs, no preview  | Draft→Publish, WYSIWYG blocks |
| Department Editor      | Manage own faculty/department | No scoped access, duplication | Scoped CRUD, limited theming  |
| Consumer App (Angular) | Read structured data          | Inconsistent schema           | Read-only APIs with filters   |

## 4. User Journeys & Flows

1. **Department Landing Creation (Editor)**

1) Editor logs in → 2. Creates Page(kind=“generic”), adds blocks & topics → 3. Submits for review → 4. Manager publishes → 5. Angular fetches published Page.

2. **Program Registration Content Update (Editor)**

1) Editor opens Program → 2. Edits overview (EN) & adds Topics → 3. Saves draft → 4. Manager approves → 5. Program visible via API.

3. **Content Import (Admin/Script)**

1) Admin uploads JSONL → 2. Importer normalizes slugs & dedups → 3. Creates entities & M2M edges → 4. Report generated.

```
[Editor] -> [Create/Update Draft] -> [Submit Review] -> [Publish] -> [Public API]
```

## 5. Functional Requirements (MoSCoW)

| ID    | Requirement                                              | Priority | Rationale        | Dependencies |
| ----- | -------------------------------------------------------- | -------- | ---------------- | ------------ |
| FR-01 | CRUD for Faculties & Departments                         | Must     | Core org graph   | DB, DRF      |
| FR-02 | CRUD for Programs w/ level & links                       | Must     | Academic catalog | Org          |
| FR-03 | Pages with JSON blocks, theming (limited), draft/publish | Must     | Headless pages   | Accounts     |
| FR-04 | Topics taxonomy, M2M with Programs/Pages                 | Must     | Classification   | Taxonomy     |
| FR-05 | Media library (assets with metadata)                     | Should   | Shared resources | Storage      |
| FR-06 | RBAC: Admin, Content Manager, Department Editor          | Must     | Governance       | Accounts     |
| FR-07 | JSON translations per entity (en/ru/kk)                  | Should   | Multilingual     | Core         |
| FR-08 | Filtering, pagination, ordering                          | Must     | API usability    | DRF          |
| FR-09 | Import JSONL → DB (idempotent)                           | Should   | Migration        | Core         |
| FR-10 | Audit/versioning for Pages                               | Could    | Traceability     | Storage      |
| FR-11 | Health checks & metrics                                  | Must     | Ops              | DevOps       |

## 6. User Stories & Acceptance Criteria

- **US-01 (Pages):** As a Content Manager, I want to publish a Page so that visitors see updated info.

  - **Gherkin:**

    - Given a Page in “draft”
    - When I change status to “published” with required fields present
    - Then the Page is readable at `/api/pages/{slug}` with `status=published`

- **US-02 (Programs):** As a Department Editor, I want to update Program overview for my faculty only.

  - **Gherkin:**

    - Given I belong to Faculty X
    - When I PATCH Program linked to Faculty X
    - Then the update succeeds; and
    - When Program belongs to Faculty Y
    - Then I receive 403 Forbidden

- **US-03 (Topics):** As a Content Manager, I want to tag a Program with Topics.

  - **Gherkin:**

    - Given Topics exist
    - When I POST Program with topics=\[“ai”]
    - Then Program-Topic relation is created and retrievable

- **US-04 (Translations):** As an Editor, I want to store EN text and add RU/KK later.

  - **Gherkin:**

    - Given translations only has “en”
    - When client requests `?lang=ru`
    - Then API returns EN fallback values with `language="ru", fallback=true` (Assumption)

## 7. Use Cases

| Use Case ID        | Actors          | Preconditions                | Triggers       | Main Flow                                       | Alternate/Exception Flows                         | Postconditions                     |
| ------------------ | --------------- | ---------------------------- | -------------- | ----------------------------------------------- | ------------------------------------------------- | ---------------------------------- |
| UC-01 Create Page  | Editor, Manager | Authenticated; role assigned | “Create Page”  | Create draft → submit → publish                 | Missing required fields → 400; Unauthorized → 403 | Page visible via API               |
| UC-02 Edit Program | Dept. Editor    | Editor scoped to faculty     | “Save Program” | Load Program → edit → save draft                | Editing other faculty → 403                       | Program updated                    |
| UC-03 Import Data  | Admin           | JSONL available              | “Run import”   | Validate → upsert entities → build M2M → report | Duplicates → merge; invalid rows → error log      | DB reflects source; report written |

## 8. Data Model & Dictionary

- **ERD (text):** Faculty 1-\* Department; Faculty 1-\* Program; Department 1-\* Program (optional); Program _-_ Topic; Page _-_ Topic. Entities carry `slug`, `translations (JSON)`, `source_url`, timestamps.;

**Data Dictionary (excerpt)**

| Entity     | Field                 | Type           | Nullable | Constraints                    | Notes                         |
| ---------- | --------------------- | -------------- | -------- | ------------------------------ | ----------------------------- |
| Faculty    | slug                  | string         | No       | unique                         | URL id                        |
| Faculty    | translations          | JSON           | No       | —                              | title, description (en/ru/kk) |
| Department | faculty               | FK(Faculty)    | No       | idx                            | Parent link                   |
| Program    | level                 | enum           | No       | {bachelor, master, phd, other} | Classification                |
| Program    | faculty               | FK(Faculty)    | No       | idx                            | Owning faculty                |
| Program    | department            | FK(Department) | Yes      | idx                            | Optional host                 |
| Page       | kind                  | enum           | No       | {about, admissions, generic}   | Page type                     |
| Page       | translations          | JSON           | No       | —                              | title, body                   |
| Page       | layout_config         | JSON           | Yes      | —                              | theme, blocks                 |
| Topic      | slug                  | string         | No       | unique                         | Tag id                        |
| MediaAsset | url                   | URL            | No       | —                              | asset store                   |
| All        | source_url            | URL            | Yes      | —                              | provenance                    |
| All        | created_at/updated_at | datetime       | No       | auto                           | timestamps                    |

## 9. APIs & Integration

- **Auth:** JWT (SimpleJWT), access TTL 60 min, refresh TTL 7 days; scopes via groups (Admin, Content Manager, Department Editor).
- **Endpoints (v1):**

| Endpoint               | Method | Purpose                  | Request Schema (excerpt)               | Response (excerpt) | Errors  | Idempotency | Rate Limits |
| ---------------------- | ------ | ------------------------ | -------------------------------------- | ------------------ | ------- | ----------- | ----------- |
| /api/faculties/        | GET    | List faculties           | `?search=&page=`                       | items\[], count    | 400     | n/a         | 60 rpm/IP   |
| /api/faculties/{slug}/ | GET    | Faculty detail           | —                                      | Faculty            | 404     | n/a         | 60 rpm/IP   |
| /api/departments/      | GET    | List (filter by faculty) | `?faculty=slug`                        | items\[], count    | 400     | n/a         | 60 rpm/IP   |
| /api/programs/         | GET    | List/filter              | `?level=&faculty=&topic=&lang=`        | items\[], count    | 400     | n/a         | 60 rpm/IP   |
| /api/programs/{slug}/  | GET    | Detail                   | `?lang=`                               | Program            | 404     | n/a         | 60 rpm/IP   |
| /api/pages/            | GET    | List/filter              | `?kind=&topic=&lang=&status=published` | items\[], count    | 400     | n/a         | 60 rpm/IP   |
| /api/pages/{slug}/     | GET    | Detail                   | `?preview_token=`(Admin)               | Page               | 404/403 | n/a         | 60 rpm/IP   |
| /api/topics/           | GET    | List topics              | `?search=`                             | items\[], count    | 400     | n/a         | 60 rpm/IP   |
| /api/media/            | POST   | Upload asset (auth)      | multipart                              | MediaAsset         | 400/413 | key=hash    | 30 rpm/user |
| /api/media/{id}/       | GET    | Asset meta               | —                                      | MediaAsset         | 404     | n/a         | 120 rpm/IP  |

- **Errors:** JSON `{code, message, details}`; standard 400/401/403/404/409/413/429/500.
- **Webhooks/Events:** _TBD_ (Phase 2: `content.published`, retry with exponential backoff, HMAC signature).
- **External Integrations:** _Assumption:_ S3-compatible storage for media; future ElasticSearch/OpenSearch.

## 10. UI/UX

- **Screens/Views:** Admin/DRF browsable API, Django Admin. _Assumption:_ minimal staff UI, primarily via Admin + future Angular.
- **Wireframe Notes:** _TBD_ (handled by frontend).
- **Accessibility:** API returns language-aware content; frontend to meet WCAG 2.1 AA. _Assumption._

## 11. Non-Functional Requirements (NFRs)

- **Performance:** p95 ≤500 ms list; p99 ≤800 ms detail; pagination default 20 items.
- **Security:** HTTPS, JWT, strong CORS allowlist, object-level permissions for scoped edits; sanitize Page blocks (HTML allowlist).
- **Privacy:** No PII beyond staff accounts; audit logs for publish actions.
- **Availability:** 99.5% monthly; zero-data-loss RPO ≤24 h; RTO ≤2 h.;
- **Reliability:** Daily backups (DB+media), weekly restore tests.
- **Scalability:** Horizontal web workers; Redis cache (Phase 2).
- **Maintainability:** Modular apps, type hints, linting, CI checks.
- **Observability:** Health endpoint, structured logs, basic APM metrics.
- **Compliance:** _Assumption:_ Institutional IT policies; GDPR-like handling for user accounts.

## 12. Constraints, Assumptions, Risks

- **Constraints:** Headless only; Django/DRF/PostgreSQL stack; MVP primarily EN content; hosting on VPS; October delivery window.;
- **Assumptions:** Owners and DevOps to be assigned; S3-compatible storage available; single IDP not required in MVP.
- **Risks & Mitigations:**

| Risk                             | Impact | Likelihood | Mitigation                                          | Owner     |
| -------------------------------- | ------ | ---------- | --------------------------------------------------- | --------- |
| Incomplete migration from Joomla | Medium | Medium     | Import dry-runs, dedup rules, manual cleanup window | Tech Lead |
| Translation delays               | Low    | High       | EN-only MVP, fallback chain                         | Content   |
| Scope creep (News/Events/Person) | Medium | Medium     | Phase gating, change control                        | PM        |
| Performance regressions          | Medium | Low        | Caching, DB indexes, profiling                      | Backend   |

## 13. Release Plan & Timeline

| Milestone              | Deliverables                                     | Owner          | Target Date    | Exit Criteria             |
| ---------------------- | ------------------------------------------------ | -------------- | -------------- | ------------------------- |
| M1: Backend Skeleton   | Repos, apps, models, migrations                  | Tech Lead      | **2025-09-05** | CI green, dev env up      |
| M2: Org & Programs API | Faculties/Departments/Programs endpoints + tests | Backend        | **2025-09-15** | CRUD + filters pass tests |
| M3: Pages & Topics     | Pages JSON blocks, Topics M2M, draft/publish     | Backend        | **2025-09-25** | Publish flow works        |
| M4: RBAC & Media       | JWT, roles, media upload                         | Backend/DevOps | **2025-10-05** | AuthZ enforced; upload ok |
| M5: Import & Hardening | JSONL import, perf passes, backups               | Backend/DevOps | **2025-10-15** | p95 ≤500 ms; backup run   |
| M6: MVP Go-Live        | Prod deploy, runbook, monitoring                 | DevOps/PM      | **2025-10-25** | Uptime ≥99.5% first week  |

- **Cut Scope Strategy:** If late: defer Media upload UI → use URLs; reduce Pages theming; postpone translations beyond EN.

## 14. Acceptance & Testing

- **Definition of Done:**

  - Code + tests merged; migrations applied; API docs updated; RBAC verified; monitoring + backups configured; runbook delivered.

- **Test Strategy:**

  - Unit (models/serializers), Integration (viewsets, filters), E2E (happy paths), Security (authz), Import dry-run tests, UAT with editors.

- **Acceptance Criteria Summary:** See Section 6 (Gherkin scenarios).

## 15. Traceability Matrix

| Requirement ID     | User Stories | Acceptance Criteria    | Test Cases        |
| ------------------ | ------------ | ---------------------- | ----------------- |
| FR-03 Pages        | US-01        | Publish visibility     | TC-PAGES-001..004 |
| FR-02 Programs     | US-02, US-03 | Scoped edit; Topic tag | TC-PROG-001..006  |
| FR-07 Translations | US-04        | Fallback behavior      | TC-I18N-001..003  |

## 16. Glossary

- **Headless CMS:** Backend-only content system with API for frontend.
- **RBAC:** Role-Based Access Control.
- **JSONL:** JSON Lines, one JSON object per line (used for import).
- **WYSIWYG Blocks:** Structured content blocks stored as JSON.

## 17. Open Questions

- **OQ-01:** Owners for Tech Lead, DevOps, Content Manager — **TBD** (PM).
- **OQ-02:** Exact HTML allowlist for Page blocks — **TBD** (Security/Backend).
- **OQ-03:** Media storage (S3 bucket & credentials) — **TBD** (DevOps).
- **OQ-04:** Preview tokens and schedule-publish requirements — **TBD** (Editors).

## 18. References

- Product Requirement Doc (headless migration context, goals, success metrics);
- KBTU Site Structure — Django Implementation Summary (entities, apps, i18n approach);
