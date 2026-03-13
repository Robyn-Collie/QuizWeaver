# Adding Source Materials (Curriculum Framework PDFs)

This document describes how to add new curriculum framework PDFs (Virginia SOL, NGSS, etc.) to QuizWeaver so that standards detail pages show Essential Knowledge, Essential Understandings, and Essential Skills.

## Primary Workflow: Claude Code Session

The fastest way to add source materials is during a Claude Code session. Claude can read any PDF visually and produce enriched JSON that the existing import pipeline handles.

### Adding a new standard set

1. Obtain the curriculum framework PDF (public document)
2. In a Claude Code session: "Read this PDF and extract all standards into `data/<set>_standards.json`"
3. Claude reads the PDF visually, produces enriched JSON matching the format below
4. Review the output (human-in-the-loop — principle 1)
5. Run: `python main.py reload-standards --set <set>`
6. Commit the JSON file

### Updating framework content for existing standards

1. In a Claude Code session: "Read this curriculum framework PDF and add Essential Knowledge/Understandings/Skills to `data/sol_standards.json`"
2. Claude reads the PDF, enriches the existing entries
3. Run: `python main.py reload-standards --set sol --force`

### Why this works

- Claude reads PDFs better than regex parsers (handles tables, multi-column layouts, grade-level format differences)
- The enriched JSON is cached in `data/` — deterministic, version-controlled, zero runtime cost
- `bulk_import_standards()` already accepts `essential_knowledge`, `essential_understandings`, and `essential_skills` fields
- The `--force` flag lets you re-extract with corrections without manual DB cleanup

## Enriched JSON Format

```json
{
  "source": "Next Generation Science Standards",
  "standard_set": "ngss",
  "version": "2013",
  "standards": [
    {
      "code": "HS-LS1-1",
      "description": "Construct an explanation based on evidence...",
      "subject": "Science",
      "grade_band": "9-12",
      "strand": "From Molecules to Organisms",
      "full_text": "Construct an explanation based on evidence for how the structure of DNA...",
      "essential_knowledge": [
        "DNA is a hierarchical molecule...",
        "The sequence of nucleotides codes for proteins..."
      ],
      "essential_understandings": [
        "All cells contain DNA...",
        "Gene expression determines cell function..."
      ],
      "essential_skills": [
        "Construct and revise an explanation...",
        "Apply concepts of statistics and probability..."
      ]
    }
  ]
}
```

The `essential_*` fields are optional — existing JSON files without them continue to work. File-level `source`, `version`, and `standard_set` fields are applied to all entries that don't override them.

## CLI Commands

```bash
# Reload a specific standard set
python main.py reload-standards --set sol

# Reload with force overwrite of existing curriculum content
python main.py reload-standards --set ngss --force

# Reload all sets that have JSON files in data/
python main.py reload-standards
```

Output example:
```
   Virginia SOL: loaded 48 standards (12 new, 36 updated)
[OK] Loaded 48 standards across 1 set(s).
```

## Legacy Workflow: PDF Upload via Web UI

The web UI upload path (`/standards` > Source Documents) still works for Virginia SOL PDFs using the regex parser in `src/source_documents.py`. This parser is tuned for the standard two-column curriculum framework layout used by VDOE.

**Limitations of the regex parser:**
- Hardcoded to Virginia SOL PDF layouts
- Grade-level PDFs (e.g., Grade 6 Science) use different formats and may not parse fully
- Adding a new state/format requires writing new parser code

For non-VA standards or any PDF with a non-standard layout, use the Claude Code workflow above.

## Step-by-step: Adding a New Subject (Legacy)

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

**Code format conventions**:
- High school courses use letter prefixes: `SOL BIO.1`, `SOL CH.3`, `SOL PS.5`, `SOL ES.7`
- Middle school standalone courses: `SOL LS.1` (Life Science), `SOL PS.1` (Physical Science)
- Grade-level science uses number + `S` suffix: `SOL 6.1S` (to distinguish from math `SOL 6.1`)

### 2. Reload standards and upload PDF

```bash
python main.py reload-standards --set sol
```

Then upload the PDF via the web UI (`/standards` > Source Documents).

### 3. Verify

- Visit `/standards` — new subject standards should appear in the list
- Click a standard (e.g., SOL PS.1) — Essential Knowledge section should be populated
- Check that the source document is listed with page numbers in the provenance section

## Troubleshooting

### "0 standards updated" after reload

The JSON codes don't match any new entries. Check that:
- Standard codes in the JSON exactly match what the DB expects
- Grade-level codes have the correct suffix (`S`, `E`, etc.)

### Re-importing doesn't duplicate data

Both the reload command and the web upload are idempotent — existing standards are updated (not duplicated), and curriculum content is only overwritten with `--force`.

## Currently loaded subjects (Virginia SOL)

| Subject | Codes | Standards | Source PDF |
|---------|-------|-----------|------------|
| Life Science | LS.1-LS.11 | 11 | life_science.pdf |
| Physical Science | PS.1-PS.9 | 9 | physical_science.pdf |
| Earth Science | ES.1-ES.12 | 12 | earth_science.pdf |
| Chemistry | CH.1-CH.7 | 7 | chemistry.pdf |
| Biology | BIO.1-BIO.8 | 8 | biology.pdf |
| Grade 6 Science | 6.1S-6.9S | 9 | science6.pdf |
