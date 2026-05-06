# User guide

## First-time setup

1. Start the stack: `docker compose up --build`.
2. Open <http://localhost:5173> and sign in with `admin@example.com` / `admin`
   (or whatever you set in `BOOTSTRAP_ADMIN_*`).
3. Open **Laboratories** and add your contracted labs (name + accreditation
   number is enough; the rest helps with expiring-accreditation alerts).
4. (Optional) Configure IMAP in `.env` and restart so new lab emails ingest
   automatically.

## Day-to-day

- **Upload page** — Drag in PDFs. Each one is OCR-processed if needed,
  fields auto-extracted, and the document indexed for RAG.
- **CoAs page** — search box hits doc code, batch, product, strain, and
  full-text. Click a row to open the detail view.
- **Detail view** — see all 15+ fields, the analytical-parameter table,
  any auto-discovered fields, the embedded PDF, and an inline RAG box
  scoped to that single CoA ("what was the THC content?", "did this batch
  pass microbial limits?", etc.).
- **RAG Ask page** — ask questions across the entire knowledge base; each
  answer cites the supporting CoAs.
- **Placeholders page** — admins review the auto-discovered field
  proposals. Approve to promote the field; deprecate to stop the
  extractor from emitting it.
- **Audit log (admins)** — every login, ingest, edit, delete with diffs.

## Sample questions for RAG Ask

- *"Which CoAs reported failures in microbial counts in the last quarter?"*
- *"Summarize the heavy-metals results for batch P050132."*
- *"Compare THC potency across all CoAs from PURELYPLANT."*
- *"Which laboratories tested the BG1024 series?"*

## Troubleshooting

- **"OCR unavailable"** in logs → the Tesseract binary isn't on PATH. The
  Docker image installs it; if running outside Docker, install
  `tesseract-ocr` and `poppler-utils`.
- **"LLM call failed; falling back to extractive answer"** → no
  `ANTHROPIC_API_KEY`, or the configured model name is wrong. Check the
  `LLM_PROVIDER` and `ANTHROPIC_MODEL` env vars.
- **Extractor missed a field** → propose a regex by adding it under
  `CANONICAL_PATTERNS` in `app/ingestion/extractor.py`, or just let the
  generic sweep catch it as a placeholder and approve it.
- **Embedding model first-load is slow** — the sentence-transformers model
  (~80 MB) downloads on first ingest. Subsequent runs are cached.
