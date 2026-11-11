# FYPHub defence preparation documents

Prepared on 11 November 2026 (Asia/Karachi) from the working repository and read-only inspection of the running database/API.

- **FYPHub_Complete_Defence_Guide.pdf** — 145 pages, with 609 PDF bookmarks for chapters, tables, APIs and source files. Best for reading and printing.
- **FYPHub_Complete_Defence_Guide.docx** — editable Word version with heading navigation, page numbering and repeating table headers.
- **FYPHub_Complete_Defence_Guide.md** — searchable text version of the same guide.
- **technical-inventory.json** — database catalog, ORM mappings, route handlers/guards, source symbols, imports, migrations and test names. Contains metadata, not student/account records.
- **preview-cover.png / preview-schema.png** — sample exported PDF pages checked for readability.

The guide contains 20 explanatory chapters plus a reading map and six generated appendices. The inventory covers 352 source/configuration files, 70 installed database tables and 264 registered route entries (including aliases/framework routes). It documents active and older alternatives separately, explains algorithms and data flows, and provides viva questions, a demonstration sequence and read-only SQL examples.

Important findings are explained in the guide: multiple Alembic heads, historical tables, incomplete upload-format signatures, frontend navigation gaps, separate proposal/evaluation stores, and deterministic rather than vector-based archive search. Existing runtime health does not prove a clean installation or a passing full test suite.

## Verification performed

- No source parsing errors in the indexed Python files.
- Actual PostgreSQL types, columns, foreign keys, checks, unique constraints and indexes collected in a read-only transaction.
- PDF opened successfully: 145 pages, no empty content pages, no detected horizontal text clipping.
- Word document opened successfully: 448 tables / 3,015 table rows; ZIP integrity valid.
- Sample pages visually inspected.
- Private .env values, passwords, session-token values, personal records and student-uploaded documents were not exported.
- Application behavior and database contents were not changed for this documentation task.

## Regenerate after changes

From the repository root, with the current backend/database container running:

```powershell
python scripts/build_defence_guide.py --build
docker cp scripts/build_defence_guide.py fyphub-p1-backend-1:/tmp/build_defence_guide.py
docker cp docs/defence fyphub-p1-backend-1:/tmp/fyphub-defence-guide
docker exec -u 0 fyphub-p1-backend-1 python /tmp/build_defence_guide.py --render /tmp/fyphub-defence-guide
docker cp fyphub-p1-backend-1:/tmp/fyphub-defence-guide/FYPHub_Complete_Defence_Guide.docx docs/defence/FYPHub_Complete_Defence_Guide.docx
docker cp fyphub-p1-backend-1:/tmp/fyphub-defence-guide/FYPHub_Complete_Defence_Guide.pdf docs/defence/FYPHub_Complete_Defence_Guide.pdf
```

The renderer uses python-docx and ReportLab already installed in the backend image. It writes only temporary/generated documentation files. The authored explanatory text is in ../FYPHub_Defence_Guide_Source.md. The generated appendices come from scripts/build_defence_guide.py. Update the inspection date and explanatory findings when regenerating for a later snapshot.
