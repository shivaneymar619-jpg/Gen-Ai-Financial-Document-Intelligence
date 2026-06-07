"""RAG engine — persistent, citation-grounded retrieval + answer generation.

Design goals:
  * PERSISTENT: chunks + embeddings live in SQLite (DocumentChunk table), so
    nothing is lost on restart — this is the fix for the original
    InMemoryVectorStore data-loss bug.
  * DEGRADES GRACEFULLY:
      - If GEMINI_API_KEY is set  -> Gemini embeddings + Gemini answer synthesis.
      - Otherwise                  -> deterministic TF-IDF retrieval + extractive
                                      answer. The app stays fully functional with
                                      zero external API calls (great for demos/CI).
  * ALWAYS CITES: every answer returns {document, page, snippet} sources.
"""
import math
import re
from collections import Counter

import numpy as np
from sqlalchemy.orm import Session

from ..config import settings
from .. import models

_WORD = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _WORD.findall(text.lower())


# ── Embeddings (optional Gemini) ───────────────────────────────────────
_embeddings_model = None
_embeddings_tried = False


def _get_embeddings():
    global _embeddings_model, _embeddings_tried
    if _embeddings_tried:
        return _embeddings_model
    _embeddings_tried = True
    if not settings.GEMINI_API_KEY:
        return None
    try:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        _embeddings_model = GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-001",
            google_api_key=settings.GEMINI_API_KEY,
        )
    except Exception:
        _embeddings_model = None
    return _embeddings_model


def embed_texts(texts: list[str]) -> list[list[float]] | None:
    model = _get_embeddings()
    if model is None:
        return None
    try:
        return model.embed_documents(texts)
    except Exception:
        return None


def embed_query(text: str) -> list[float] | None:
    model = _get_embeddings()
    if model is None:
        return None
    try:
        return model.embed_query(text)
    except Exception:
        return None


# ── Retrieval ──────────────────────────────────────────────────────────
def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) or 1e-9
    return float(np.dot(a, b) / denom)


def _tfidf_scores(query: str, chunks: list[models.DocumentChunk]) -> list[float]:
    """Classic TF-IDF cosine — no external services required."""
    docs_tokens = [_tokenize(c.content) for c in chunks]
    q_tokens = _tokenize(query)
    N = len(chunks) or 1

    df = Counter()
    for toks in docs_tokens:
        for t in set(toks):
            df[t] += 1

    def idf(t):
        return math.log((N + 1) / (df.get(t, 0) + 1)) + 1.0

    def vec(tokens):
        tf = Counter(tokens)
        return {t: (tf[t] / max(len(tokens), 1)) * idf(t) for t in tf}

    qv = vec(q_tokens)
    qnorm = math.sqrt(sum(v * v for v in qv.values())) or 1e-9

    scores = []
    for toks in docs_tokens:
        dv = vec(toks)
        dot = sum(qv.get(t, 0) * dv.get(t, 0) for t in qv)
        dnorm = math.sqrt(sum(v * v for v in dv.values())) or 1e-9
        scores.append(dot / (qnorm * dnorm))
    return scores


def retrieve(db: Session, owner_id: str, query: str, k: int = None) -> list[tuple[models.DocumentChunk, float]]:
    """Return up to k (chunk, score) pairs for this user's documents."""
    k = k or settings.RETRIEVE_K
    chunks = (
        db.query(models.DocumentChunk)
        .filter(models.DocumentChunk.owner_id == owner_id)
        .all()
    )
    if not chunks:
        return []

    qvec = embed_query(query)
    if qvec is not None and all(c.embedding for c in chunks):
        q = np.array(qvec, dtype=float)
        scored = [(c, _cosine(q, np.array(c.embedding, dtype=float))) for c in chunks]
    else:
        scores = _tfidf_scores(query, chunks)
        scored = list(zip(chunks, scores))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:k]


# ── Answer synthesis ───────────────────────────────────────────────────
def _llm_answer(question: str, context: str, history: list[dict]) -> str | None:
    if not settings.GEMINI_API_KEY:
        return None
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

        llm = ChatGoogleGenerativeAI(
            model=settings.LLM_MODEL, temperature=0, google_api_key=settings.GEMINI_API_KEY
        )
        system = (
            "You are an expert AI financial analyst assistant. Use ONLY the retrieved "
            "context to answer. If the answer isn't in the context, say you don't know. "
            "Be concise and professional. Cite figures exactly as written.\n\n"
            f"Context:\n{context}"
        )
        msgs = [SystemMessage(content=system)]
        for h in history[-6:]:
            if h["role"] == "user":
                msgs.append(HumanMessage(content=h["content"]))
            else:
                msgs.append(AIMessage(content=h["content"]))
        msgs.append(HumanMessage(content=question))
        return llm.invoke(msgs).content
    except Exception:
        return None


def _extractive_answer(question: str, hits: list[tuple[models.DocumentChunk, float]]) -> str:
    """Deterministic fallback: surface the most relevant passages."""
    if not hits:
        return "I couldn't find anything relevant in your uploaded documents."
    top = hits[0][0]
    lead = top.content.strip().replace("\n", " ")
    lead = (lead[:500] + "…") if len(lead) > 500 else lead
    return (
        f"Based on the most relevant passage in **{top.document.filename}** "
        f"(page {top.page}):\n\n> {lead}\n\n"
        f"_(Set GEMINI_API_KEY to enable full natural-language answer synthesis. "
        f"Citations above are exact source references.)_"
    )


def answer(db: Session, owner_id: str, question: str, history: list[dict] = None):
    """Return (answer_text, sources, confidence)."""
    history = history or []
    hits = retrieve(db, owner_id, question)
    if not hits:
        return (
            "No documents found. Upload and process a document first, then ask again.",
            [], 0.0,
        )

    context = "\n\n---\n\n".join(
        f"[{c.document.filename} p.{c.page}]\n{c.content}" for c, _ in hits
    )
    sources = [
        {
            "document": c.document.filename,
            "page": c.page,
            "snippet": (c.content.strip().replace("\n", " ")[:200] + "…"),
        }
        for c, _ in hits
    ]
    confidence = round(float(max(0.0, min(1.0, hits[0][1]))), 3)

    text = _llm_answer(question, context, history) or _extractive_answer(question, hits)
    return text, sources, confidence
