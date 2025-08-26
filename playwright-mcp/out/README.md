# KBTU Website Structure Documentation

This directory contains the structured data extracted from the KBTU website (kbtu.edu.kz) in English.

## Data Files

1. **faculties.jsonl** - Contains information about the schools/faculties at KBTU
2. **departments.jsonl** - Contains information about departments within faculties
3. **programs.jsonl** - Contains information about academic programs offered
4. **pages.jsonl** - Contains information about key pages on the website
5. **topics.jsonl** - Contains academic topics/areas of study
6. **edges.jsonl** - Contains relationships between entities (e.g., which faculty offers which program)
7. **_report.json** - Summary statistics of the crawling process

## Entity Relationships

The following relationships are represented in the edges.jsonl file:

- Faculties offer Programs
- Faculties have Departments
- Programs belong to Topics

## Data Format

Each entity follows a standardized format with the following fields:

- `id`: A unique identifier for the entity
- `translations`: An array of translated content with `lang` and `title` fields
- `source_url`: The original URL where the information was found
- `_ts_utc`: Timestamp of when the data was collected

## Notes

- All data was collected from the English version of the KBTU website
- One broken link was encountered for the International School of Economics
- The structure represents undergraduate programs primarily, as that was the focus of the crawling