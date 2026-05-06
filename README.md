# CoA Tracker — Ingest, Track, RAG, Discover Placeholders

A self-hosted application for ingesting, processing, tracking, and querying
**Certificates of Analysis (CoAs)** for pharmaceutical / cannabis / regulated-
product QC. It auto-extracts structured fields from incoming PDFs (electronic
or scanned), builds a semantic index for **RAG**-style Q&A, and keeps a
review queue of newly-discovered fields ("placeholders") so the data model
adapts as new lab formats arrive.

## Features

- **Ingestion** — Drag-and-drop upload, IMAP email polling, Drive bulk
  import, REST API. Direct PDF text extraction with **OCR** (Tesseract)
  fallback for scanned documents.
- **Auto-extraction** — Regex + heuristic extractor pulls doc code, batch
  number, sample ID, product/strain/potency, lab name + accreditation,
  receipt/start/completion dates, and an analytical-parameter table.
- **Placeholder discovery** — Any new `Label: Value` field that doesn't map
  to a canonical column is added to the **placeholder review queue** with
  occurrence counts. Admins approve, edit, or deprecate them.
- **RAG over CoAs** — Each PDF is chunked, embedded with
  `sentence-transformers/all-MiniLM-L6-v2` (384-dim), and stored in
  `pgvector`. The `/rag/ask` endpoint retrieves the top-K passages and
  synthesizes an answer with Anthropic Claude (or returns an extractive
  fallback if no API key is set).
- **Search & filter** — Full-text search via Postgres tsvector + GIN index,
  filter by lab, date range, status, ingestion method.
- **Audit trail (ALCOA+)** — Append-only `audit_log` table with a trigger
  that blocks updates/deletes; logs every login, ingest, create, update,
  delete with actor + before/after diff.
- **Role-based access** — `admin` / `analyst` / `viewer`; default
  bootstrap admin is created on first start.
- **Embedded PDF viewer + per-CoA RAG** — view the source PDF and ask
  follow-up questions about that single document.

## Quick start

```bash
git clone <repo> && cd Kade
cp .env.example .env             # edit JWT_SECRET, ANTHROPIC_API_KEY, IMAP_*
docker compose up --build
```

- Web UI:  <http://localhost:5173>
- API docs: <http://localhost:8000/docs>
- Default admin: `admin@example.com` / `admin` (override with
  `BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD`).

## Bulk-ingest the sample Drive folders

The repo includes `scripts/seed_from_drive.py` for pulling a public Drive
folder into the running app:

```bash
pip install gdown httpx
python scripts/seed_from_drive.py \
  --folder-url 'https://drive.google.com/drive/folders/18Egoy3N5CDRlpHsPIPtFnb--19UEY9NU' \
  --api http://localhost:8000 \
  --email admin@example.com --password admin
```

For private folders, share the folder with a Google service account and
pass `--service-account creds.json`.

## Architecture

```
┌─────────────┐  PDF (email / upload / scan / Drive)
│  Frontend   │──▶ POST /coas/upload ──┐
│  React+Vite │                        ▼
└─────────────┘                 ┌──────────────────────┐
                                │  PDF + OCR pipeline   │ PyMuPDF, Tesseract
                                └──────────┬───────────┘
                                           ▼
                                ┌──────────────────────┐
                                │  Field extractor      │ regex + heuristics
                                │  + placeholder sweep  │ proposes new fields
                                └──────────┬───────────┘
                                           ▼
                                ┌──────────────────────┐
                                │  Chunker + Embedder   │ sentence-transformers
                                └──────────┬───────────┘
                                           ▼
                                ┌──────────────────────┐
                                │  PostgreSQL + pgvector│ FTS, JSONB, audit
                                └──────────┬───────────┘
                                           ▼
                                ┌──────────────────────┐
                                │  RAG retriever + LLM  │ cosine + Anthropic
                                └──────────────────────┘
```

## API surface

| Method   | Path                         | Notes                              |
|----------|------------------------------|------------------------------------|
| POST     | `/auth/login`                | JWT bearer                         |
| GET      | `/auth/me`                   |                                    |
| GET      | `/coas`                      | search, filter, paginate           |
| POST     | `/coas`                      | create (analyst+)                  |
| GET      | `/coas/{id}`                 | full record + parameters           |
| PATCH    | `/coas/{id}`                 | update; bumps version              |
| DELETE   | `/coas/{id}`                 | admin only                         |
| GET      | `/coas/{id}/file`            | download original PDF              |
| POST     | `/coas/upload` (multipart)   | ingest + extract + index           |
| POST     | `/drive/ingest`              | pull public Drive PDFs by file id  |
| GET      | `/laboratories`              |                                    |
| POST     | `/laboratories`              | create lab profile                 |
| GET/POST | `/placeholders`              | review queue + manual creation     |
| POST     | `/placeholders/{id}/decision`| approve / deprecate                |
| POST     | `/rag/ask`                   | retrieval + LLM synthesis          |
| GET      | `/dashboard/summary`         |                                    |
| GET      | `/audit`                     | admin only                         |

Full OpenAPI: <http://localhost:8000/docs>.

## Placeholder model

Every PDF is swept for `Label: Value` patterns. Anything that's not a
canonical field becomes a candidate. Unseen candidates are inserted into
`placeholder_fields` with `status='proposed'`; matches against existing
proposals increment `occurrence_count` so the most-frequent unmodelled
fields surface first. Admins approve them on the **Placeholders** page,
turning them into first-class fields stored in `coas.extra_fields`.

This means the system **adapts** as new lab formats appear — no schema
migration needed for the long tail of QC parameters.

## Compliance notes (ALCOA+)

- Append-only `audit_log` (DB trigger rejects UPDATE/DELETE).
- `coas.version` increments on every PATCH; `superseded_by` lets you
  link supersession chains.
- File hashes (`file_sha256`) prevent silent re-ingestion of the same PDF.
- All extracted text is preserved in `coas.extracted_text` (capped) and
  in chunked form in `coa_chunks` so you can reproduce reads.

## Repo layout

```
backend/                FastAPI app (Python 3.12)
  app/api/              HTTP routers
  app/core/             config, security
  app/db/               SQLAlchemy session
  app/models/           ORM
  app/schemas/          Pydantic
  app/services/         orchestration (ingestion, audit)
  app/ingestion/        PDF + OCR + field extractor + email poller
  app/rag/              chunker, embedder, retriever, LLM
  db/init/001_schema.sql initial DDL (auto-applied by Postgres entrypoint)
frontend/               React 18 + Vite + Tailwind
docker-compose.yml      db + backend + frontend
scripts/seed_from_drive.py
```

## Configuration

See `.env.example`. Key knobs:

- `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` — for RAG answer synthesis.
  Without a key the system returns an extractive fallback.
- `IMAP_HOST`, `IMAP_USER`, `IMAP_PASSWORD`, `IMAP_FOLDER` — turn on the
  background email poller. Polls every `IMAP_POLL_SECONDS` seconds.
- `EMBEDDING_MODEL` — defaults to MiniLM-L6 (384 dims). If you change this,
  also change `EMBEDDING_DIM` and the `vector(384)` column type.
- `BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD` — used only when
  the `users` table is empty on startup.

## Roadmap

- LLM-assisted extraction for messy scanned CoAs (currently regex-first).
- Per-laboratory extraction templates (overrides regex when known).
- Webhook on ingest for downstream LIMS integration.
- Signed URL for PDF download (currently auth via header).
