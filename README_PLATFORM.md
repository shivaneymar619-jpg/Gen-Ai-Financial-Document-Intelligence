# FinDocAI — Full-Stack Platform 🏦

> The enterprise MVP build of the GenAI Financial Document Intelligence system.
> This is the **full-stack web platform** (FastAPI + SPA) that supersedes the
> original single-file Streamlit prototype (`app.py`, still present and runnable).

---

## What this is

A runnable, multi-user RAG platform implementing the MVP specification's core
feature set. It runs on **localhost with zero external services** — SQLite,
local disk storage, and a built-in TF-IDF retriever mean it works out of the box.
Add a `GEMINI_API_KEY` to upgrade to real LLM embeddings + answer synthesis.

### Quick start

```bash
pip install -r requirements.txt        # backend deps (FastAPI, SQLAlchemy, bcrypt, ...)
python run.py                          # serves on http://localhost:8000
```

Then open:
- **http://localhost:8000/**     → marketing landing page
- **http://localhost:8000/app**  → the application (register an account, upload, chat)
- **http://localhost:8000/docs** → interactive OpenAPI docs (Swagger UI)

> Optional: copy `.env.example` to `.env` and set `GEMINI_API_KEY` to enable
> Gemini embeddings + natural-language answer synthesis. Without it the app uses
> a deterministic TF-IDF retriever and extractive answers (fully functional).

---

## Architecture

```text
 Browser SPA (webapp/app.html, mobile-first, Tailwind)
        │  fetch + JWT / X-API-Key
        ▼
 FastAPI  (backend/app/main.py)  ──►  36 routes under /api
        │
        ├── auth        JWT (15m access / 7d refresh), bcrypt, API keys
        ├── documents   upload → async processing (BackgroundTasks) → soft delete
        ├── chat        multi-turn RAG, citation-grounded, confidence scores
        ├── teams       workspaces + role-based membership
        ├── audit       append-only compliance log + CSV export
        ├── analytics   usage metrics, freemium status, activity chart
        └── templates   reusable query sets (invoice / statement / loan)
        │
        ▼
 RAG service (services/rag_service.py)
        │   Gemini embeddings  ──or──  TF-IDF fallback (no API key needed)
        ▼
 Persistent store: SQLite (document_chunks table holds text + embeddings)
```

### Key design decisions (pragmatic swaps, all config-level to scale up)

| Spec component        | This build                    | How to scale up                          |
|-----------------------|-------------------------------|------------------------------------------|
| PostgreSQL            | SQLite (SQLAlchemy ORM)       | Set `DATABASE_URL=postgresql+psycopg://…` |
| Redis + Celery        | FastAPI `BackgroundTasks`     | Swap `_process_in_background` for a Celery task |
| AWS S3                | local disk (`backend/data/uploads`) | Replace storage write with `boto3`   |
| ChromaDB              | SQLite-backed vector store    | Embeddings already abstracted in `rag_service` |
| React + TS build      | vanilla-JS SPA + Tailwind CDN | No build step; port components 1:1 to React |

---

## The original bug this fixes

The prototype's `src/vector_store.py` used `InMemoryVectorStore` — **all embeddings
were lost on every restart**, making it unusable for more than one session.

This build persists every chunk and its embedding in the `document_chunks` table.
Verified: after a full server restart, documents stay `ready`, chunks remain
indexed, and chat still returns citations.

---

## Feature checklist (MVP spec)

- [x] **Auth** — register/login/refresh, JWT, bcrypt(12), password policy
- [x] **API keys** — create/list/revoke, `X-API-Key` auth for integrations
- [x] **Documents** — batch upload, OCR/PDF/text extraction, async processing, soft-delete + restore, reprocess
- [x] **RAG chat** — multi-turn sessions, exact source citations (doc + page), confidence scores
- [x] **Persistent vector store** — survives restart (fixes in-memory bug)
- [x] **Teams** — workspaces, role-based membership (owner/admin/member)
- [x] **Audit trail** — immutable, searchable, CSV export (SOX/GDPR-oriented)
- [x] **Analytics** — overview metrics + 14-day activity chart
- [x] **Freemium** — 10 docs / 100 queries per month on free plan, 402 past limit
- [x] **Templates** — starter sets for invoices, bank statements, loan agreements
- [x] **Frontend** — mobile-first SPA (bottom-tab nav) + responsive desktop sidebar

### Honestly not included (would need real infra / more time)
- WebSocket live collaboration & presence (REST chat works; sockets are additive)
- Stripe billing integration (plan field + limits exist; no payment flow)
- Production Docker Compose / CI-CD / load testing
- React/TypeScript rewrite (current SPA is vanilla JS, same UX)

---

## Project layout

```text
backend/
  app/
    main.py            FastAPI app, router mounts, serves SPA
    config.py          env-driven settings
    database.py        SQLAlchemy engine/session
    models.py          11-table schema (users, documents, chunks, chat, audit, …)
    schemas.py         Pydantic request/response models
    security.py        bcrypt + JWT + API-key hashing
    deps.py            current-user, audit, freemium enforcement
    services/
      extraction.py    PDF/OCR/text → pages → chunks
      rag_service.py   embeddings + retrieval + answer (Gemini or TF-IDF)
      document_service.py   ingestion pipeline (persists chunks + vectors)
    routers/           auth, documents, chat, teams, audit, analytics, templates
  data/                SQLite db, uploads, server logs (gitignored)
webapp/
  index.html           marketing landing page
  app.html             single-page application
run.py                 dev launcher (uvicorn)
.env.example           configuration template
```

## Sample queries to try

- "What is the total amount due?"
- "What are the payment terms and late fee?"
- "Summarize the risks in this document."
- "What is the interest rate and repayment schedule?"
