# Сущности и связи — KBTU Headless CMS (Backend)

Коротко: мы строим **headless-бэкенд на Django/DRF** с нормализованными сущностями (факультеты, департаменты, образовательные программы, страницы, темы/теги, медиа) и минимальными дубликатами. Фронт (Angular) будет просто читать эти API.&#x20;

---

## Что является чем (каталог сущностей)

| Сущность       | Минимальные поля                                                                 | Зачем нужна                                       | Основные связи                                                          |                                                           |                                                            |                                                                    |
| -------------- | -------------------------------------------------------------------------------- | ------------------------------------------------- | ----------------------------------------------------------------------- | --------------------------------------------------------- | ---------------------------------------------------------- | ------------------------------------------------------------------ |
| **Faculty**    | `slug`, `translations{title,description}`, `source_url`, `created_at/updated_at` | Школа/факультет как верхний уровень структуры     | 1→\* **Department**, 1→\* **Program**                                   |                                                           |                                                            |                                                                    |
| **Department** | `faculty(FK)`, `slug`, `translations`, `source_url`                              | Кафедра/департамент внутри факультета             | _→1 **Faculty**; 1→_ **Program** (опц.)                                 |                                                           |                                                            |                                                                    |
| **Program**    | `slug`, \`level{bachelor                                                         | master                                            | phd}`, `faculty(FK)`, `department(FK?)`, `translations`, `source_url\`  | Образовательная программа                                 | \*→1 **Faculty**; \*→1 **Department**(опц.); _↔_ **Topic** |                                                                    |
| **Page**       | `slug`, \`kind{about                                                             | admissions                                        | generic}`, `translations{title,body}`, `layout_config(JSON)`, `status\` | Контентные страницы (лендинги), редактируются редакторами | _↔_ **Topic** (классификация)                              |                                                                    |
| **Topic**      | `slug`, `translations{title}`, `source_url`                                      | Таксономия (теги/темы) для фильтров и группировок | _↔_ **Program**, _↔_ **Page**                                           |                                                           |                                                            |                                                                    |
| **MediaAsset** | `url`, \`kind{image                                                              | pdf                                               | doc                                                                     | ...}`, `title?`, `credit?`, `w,h?`, `source_url\`         | Единая медиатека без дубликатов                            | FK из **Page/Program** при необходимости (геро-картинка, вложение) |

**Единые принципы:** все сущности имеют `slug` (URL-идентификатор), `translations` (JSON для en/ru/kk) и `source_url` (первичный источник/след миграции) — это важно для **shared resource management** и повторного использования данных без копий.&#x20;

---

## Как они связаны (словами)

- **Faculty** содержит много **Department** и много **Program**.&#x20;
- **Department** опционально «хостит» **Program** (если программа привязана к конкретной кафедре).&#x20;
- **Program** и **Page** классифицируются через _многие-ко-многим_ с **Topic** (теги: “AI”, “Finance”, и т.п.).&#x20;
- **MediaAsset** не дублируется: подключается к контенту ссылками/внешними ключами (картинки, PDF).&#x20;

---

## Диаграмма (ER, Mermaid)

```mermaid
erDiagram
    FACULTY ||--o{ DEPARTMENT : has
    FACULTY ||--o{ PROGRAM    : offers
    DEPARTMENT ||--o{ PROGRAM : hosts_optional
    PROGRAM  }o--o{ TOPIC     : tagged_as
    PAGE     }o--o{ TOPIC     : tagged_as

    FACULTY { string slug UK, json translations, string source_url, datetime created_at, datetime updated_at }
    DEPARTMENT { string slug UK, json translations, string source_url, string faculty_id FK }
    PROGRAM { string slug UK, enum level, json translations, string source_url, string faculty_id FK, string department_id FK }
    PAGE { string slug UK, enum kind, json translations, json layout_config, enum status, string source_url }
    TOPIC { string slug UK, json translations, string source_url }
```

_(По необходимости MediaAsset добавляется как отдельные FK/ссылки из Page/Program, чтобы не плодить файлы.)_&#x20;

---

## Почему так (ключевые правила моделирования)

- **Headless и без дублей:** отдельные канонические сущности + связи вместо копипаста (напр., одна **Program** может появляться в разных лендингах через ссылки). Это упрощает консистентность и повторное использование.&#x20;
- **Таксономии/Topics:** сквозные теги для страниц и программ дают фильтры и подборки без новых таблиц.&#x20;
- **Мультиязычность:** `translations` как JSON на сущности (EN уже собран, RU/KK добавятся позже), с fallback на EN.&#x20;
- **Расширяемость:** легко добавить **Person**, **News**, **Event** во 2-й фазе, не ломая ядро (они будут ссылаться на Faculty/Department/Topic).&#x20;

---

## Границы модулей (Django apps)

- `org` — **Faculty**, **Department** (организационная иерархия).&#x20;
- `programs` — **Program** (+ связи с org и taxonomy).&#x20;
- `pages` — **Page** (контентные блоки, статус draft/published).&#x20;
- `taxonomy` — **Topic** (общая классификация).&#x20;
- `media` — **MediaAsset** (медиатека).&#x20;
- `core` — общие базовые модели (`TimeStamped`, `translations JSON`).&#x20;
- `accounts` — роли/права (RBAC) для редактирования (контент-менеджеры, редакторы департаментов).&#x20;

---

## Коротко об API-ресурсах (для ориентира)

- `/api/faculties/`, `/api/faculties/{slug}` — список/деталь.
- `/api/departments/?faculty=slug` — департаменты по факультету.
- `/api/programs/?level=&faculty=&topic=` — каталог программ с фильтрами.
- `/api/pages/?kind=&topic=` и `/api/pages/{slug}` — страницы и лендинги.
- `/api/topics/` — таксономии.
  _(Фронт будет читать опубликованные данные; редактирование/публикация — по ролям.)_&#x20;

---

## Что добавить потом (расширения)

- **Person** (профили ППС, привязки к департаментам/темам).
- **News/Event** (новости/мероприятия с привязками к темам/людям/подразделениям).
  Эти сущности будут **упоминать** уже существующие Faculty/Department/Topic, сохраняя принцип shared resources.&#x20;

---

Если нужно, могу вынести это как отдельный `Entities-and-Relationships.md` для репозитория и добавить вариант ER-диаграммы с **MediaAsset** и будущими **Person/News/Event**.
