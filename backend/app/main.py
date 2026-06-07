"""FastAPI application entrypoint.

Mounts all API routers under /api and serves the mobile-first SPA frontend.
Run with:  python -m uvicorn backend.app.main:app --reload --port 8000
(or use the run.py helper at the project root).
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import init_db
from .routers import auth, documents, chat, teams, audit, analytics, templates

app = FastAPI(
    title="FinDocAI API",
    version="1.0.0",
    description="GenAI-powered financial document intelligence — RAG with citations.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    init_db()


@app.get("/api/health", tags=["meta"])
def health():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "llm_enabled": bool(settings.GEMINI_API_KEY),
        "mode": "gemini" if settings.GEMINI_API_KEY else "tfidf-fallback",
    }


for r in (auth, documents, chat, teams, audit, analytics, templates):
    app.include_router(r.router, prefix=settings.API_PREFIX)


# ── Serve frontend SPA ─────────────────────────────────────────────────
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "webapp"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    def serve_index():
        return FileResponse(str(FRONTEND_DIR / "index.html"))

    @app.get("/app")
    def serve_app():
        return FileResponse(str(FRONTEND_DIR / "app.html"))
