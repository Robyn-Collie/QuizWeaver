# Adding Source Materials (Curriculum Framework PDFs)

This document describes how to add new Virginia SOL Curriculum Framework PDFs to QuizWeaver so that standards detail pages show Essential Knowledge, Essential Understandings, and Essential Skills extracted from official VDOE documents.

## Overview

The pipeline has two parts:

1. **Standards data** (`data/sol_standards.json`) — the master list of SOL codes, descriptions, and metadata. The source document importer matches extracted codes against this list, so any code referenced in a PDF must exist here first.
2. **Source document import** — PDFs are uploaded via the web UI or processed via script. The parser extracts structured content and links it to standards with full provenance (page numbers, source document).

## Step-by-step: Adding a New Subject

### 1. Verify standard codes exist in `sol_standards.json`

Open `data/sol_standards.json` and check that every SOL code the PDF references has an entry. Each entry needs:

```json
{
  "code": "SOL XX.1",
  "description": "Short description",
  "subject": "Science",
  "grade_band": "9-12",
  "strand": "Subject Name",
  "full_text": "The student will investigate and understand..."
}
```

**Where to find descriptions**: The curriculum framework PDFs themselves contain the standard declaration text (e.g., "PS.1 The student will demonstrate..."). You can also cross-reference with the [VDOE Science SOL page](https://www.doe.virginia.gov/teaching-learning-assessment/k-12-standards-instruction/science/standards-of-learning).

**Code format conventions**:
- High school courses use letter prefixes: `SOL BIO.1`, `SOL CH.3`, `SOL PS.5`, `SOL ES.7`
- Middle school standalone courses: `SOL LS.1` (Life Science), `SOL PS.1` (Physical Science)
- Grade-level science uses number + `S` suffix: `SOL 6.1S` (to distinguish from math `SOL 6.1`)
- Grade-level science (old format) uses `E` suffix: `SOL 6.1E`
- The `_find_standard()` function handles fallback: if a PDF extracts `SOL 6.1`, it tries `SOL 6.1S` then `SOL 6.1E`

### 2. Commit and push the updated JSON

```bash
git add data/sol_standards.json
git commit -m "feat: add [Subject] standards to sol_standards.json"
git push
```

### 3. Pull on Chopper and reload standards

```bash
ssh robyn@100.94.23.39
cd /opt/quizweaver && git pull
source .venv/bin/activate

python -c "
from src.database import get_engine, init_db, get_session
from src.standards import load_standard_set
engine = get_engine('quiz_warehouse.db')
init_db(engine)
session = get_session(engine)
count = load_standard_set(session, 'sol')
print(f'Standards imported: {count}')
session.close()
engine.dispose()
"
```

`load_standard_set` is additive — it inserts new codes and skips existing ones. No data is lost.

### 4. Upload the PDF

**Option A: Web UI** (preferred for single files)
1. Go to `/standards` and click "Source Documents"
2. Upload the curriculum framework PDF
3. The system parses it automatically and shows how many standards were updated

**Option B: Script** (for batch re-import of all documents)

```bash
python -c "
from src.database import get_engine, init_db, get_session
from src.source_documents import (
    list_source_documents, extract_columns_by_page,
    parse_sol_curriculum_framework, import_from_source_document,
)
engine = get_engine('quiz_warehouse.db')
init_db(engine)
session = get_session(engine)
docs = list_source_documents(session)
for doc in docs:
    pages = extract_columns_by_page(f'data/source_documents/{doc.filename}')
    parsed = parse_sol_curriculum_framework(pages)
    count = import_from_source_document(session, doc.id, parsed)
    print(f'{doc.title}: {count} standards updated')
session.close()
engine.dispose()
"
```

### 5. Restart the service

```bash
sudo systemctl restart quizweaver
```

### 6. Verify

- Visit `/standards` — new subject standards should appear in the list
- Click a standard (e.g., SOL PS.1) — Essential Knowledge section should be populated
- Check that the source document is listed with page numbers in the provenance section

## Troubleshooting

### "0 standards updated" after import

The PDF's SOL codes don't match any entries in `sol_standards.json`. Debug with:

```bash
python -c "
from src.source_documents import extract_columns_by_page, parse_sol_curriculum_framework
pages = extract_columns_by_page('data/source_documents/FILENAME.pdf')
parsed = parse_sol_curriculum_framework(pages)
for p in parsed:
    print(f'{p[\"code\"]} (page {p[\"page\"]})')
"
```

Compare the extracted codes against `sol_standards.json` entries. Common mismatches:
- Grade-level codes missing `S` or `E` suffix
- Different prefix format (e.g., `SOL 6.1` vs `SOL 6.1E`)

### PDF only parses 1 standard or has missing content

The parser (`parse_sol_curriculum_framework`) is tuned for the standard two-column curriculum framework layout used by VDOE for high school and middle school courses. Grade-level PDFs (e.g., Grade 6 Science) may use a different layout. Check the regex patterns in `src/source_documents.py` around line 352.

### Re-importing doesn't duplicate data

The import is idempotent — `_update_standard_json_cache()` deduplicates content items by text, and `import_from_source_document()` checks for existing excerpts before creating new ones.

## Currently loaded subjects

| Subject | Codes | Standards | Source PDF |
|---------|-------|-----------|------------|
| Life Science | LS.1–LS.11 | 11 | life_science.pdf |
| Physical Science | PS.1–PS.9 | 9 | physical_science.pdf |
| Earth Science | ES.1–ES.12 | 12 | earth_science.pdf |
| Chemistry | CH.1–CH.7 | 7 | chemistry.pdf |
| Biology | BIO.1–BIO.8 | 8 | biology.pdf |
| Grade 6 Science | 6.1S–6.9S | 9* | science6.pdf |

*Grade 6 PDF uses a different layout; only 1 standard parsed currently. Parser may need adjustment for grade-level format.
