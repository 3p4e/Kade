# Architecture notes

## Data flow

1. **Upload / Email / Drive** — A PDF arrives via one of:
   - `POST /coas/upload` (multipart), called from the React UI's Upload page.
   - Background IMAP poller (`app.ingestion.email_poller`) that scans an
     inbox for unread messages with PDF attachments.
   - `POST /drive/ingest` (Google Drive public file IDs).
2. **Storage** — `services.ingestion_service.store_uploaded_pdf` writes
   bytes to `${DATA_DIR}/<source>/YYYY/MM/DD/<safe-filename>`. The file's
   SHA-256 is recorded so duplicates can be flagged.
3. **Text extraction** — `ingestion.pdf.extract_pages` opens with
   PyMuPDF; if the document is empty (likely scanned), it falls back to
   `pdf2image` + Tesseract OCR.
4. **Field extraction** — `ingestion.extractor.extract` runs:
   1. Canonical regex patterns for the 15+ known fields.
   2. A generic `Label: Value` sweep over every line.
   3. Cross-references the sweep against `placeholder_fields` and emits
      candidate records for any new keys.
5. **Indexing** — `rag.chunker.chunk_pages` produces ~900-character
   chunks with 150-char overlap. `rag.embedder` embeds them with
   sentence-transformers (MiniLM, 384 dims). Chunks land in
   `coa_chunks` with the `embedding vector(384)` column.
6. **Persistence** — Coa, parameters, and any newly-discovered placeholders
   are written in a single transaction. An `audit_log` row records the
   ingest.

## RAG retrieval

`POST /rag/ask` embeds the question, runs an HNSW cosine search against
`coa_chunks.embedding`, and returns the top-K passages joined back to
their parent CoA. If `ANTHROPIC_API_KEY` is set, the passages plus the
question are sent to Claude with a strict system prompt
("answer using only these passages, cite [1], [2]"). Without an API key
the answer is the closest passage verbatim, so the system is functional
fully offline.

## Placeholder lifecycle

- **proposed** — auto-discovered, awaits admin review.
- **approved** — admins promote a placeholder; the extractor coerces
  matching values to the declared `data_type` (string/number/date/bool).
  Approved placeholders still live in `coas.extra_fields` (JSONB), but
  they're indexed and listable.
- **deprecated** — extractor stops promoting them; existing `extra_fields`
  rows are untouched.

To turn a high-traffic placeholder into a first-class column you'd
write a migration that copies `extra_fields ->> 'key'` into a new
column and drop the placeholder. This is intentionally manual to keep
schema changes auditable.

## Compliance / ALCOA+

| Principle      | How it's enforced                                                       |
|----------------|-------------------------------------------------------------------------|
| Attributable   | JWT auth → `created_by`/`updated_by` columns + audit_log.actor_id       |
| Legible        | Full text preserved in `extracted_text` and in chunked form             |
| Contemporaneous| All writes use `now()` server-side; no client timestamps trusted        |
| Original       | Original PDF stored on disk + SHA-256 hash recorded                     |
| Accurate       | Field values can be PATCHed; old values preserved in `audit_log.before` |
| Complete       | `audit_log.after` snapshots changed fields; `version` bumps on edit     |
| Consistent     | Atomic transactions per ingest; `before/after` ordering preserved       |
| Enduring       | `audit_log` is append-only — DB trigger rejects UPDATE/DELETE           |
| Available      | API + UI provide search/filter; PDFs streamed via `/coas/{id}/file`     |

## Why pgvector and not a separate vector DB?

CoA volumes are typically O(10⁴–10⁵), well within Postgres' comfort zone
when paired with an HNSW index. Keeping vectors next to the relational
data simplifies joins (chunk → coa → lab), backup, and ALCOA+ retention,
and removes a moving part. If volumes grow past ~10M chunks, swap in
Qdrant/Weaviate by replacing `app/rag/retriever.py` and the embed call site.
