"""Usage analytics + freemium status for the dashboard."""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from .. import models
from ..config import settings
from ..deps import get_current_user, current_period

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview")
def overview(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    period = current_period()

    def usage(metric):
        rec = db.query(models.UsageMetric).filter(
            models.UsageMetric.user_id == user.id,
            models.UsageMetric.metric == metric,
            models.UsageMetric.period == period,
        ).first()
        return rec.value if rec else 0

    total_docs = db.query(func.count(models.Document.id)).filter(
        models.Document.owner_id == user.id, models.Document.deleted_at.is_(None)
    ).scalar()
    ready_docs = db.query(func.count(models.Document.id)).filter(
        models.Document.owner_id == user.id, models.Document.status == "ready",
        models.Document.deleted_at.is_(None),
    ).scalar()
    total_chunks = db.query(func.count(models.DocumentChunk.id)).filter(
        models.DocumentChunk.owner_id == user.id
    ).scalar()
    total_sessions = db.query(func.count(models.ChatSession.id)).filter(
        models.ChatSession.owner_id == user.id, models.ChatSession.deleted_at.is_(None)
    ).scalar()
    total_messages = db.query(func.count(models.Message.id)).join(
        models.ChatSession, models.Message.session_id == models.ChatSession.id
    ).filter(models.ChatSession.owner_id == user.id).scalar()

    docs_used = usage("documents_uploaded")
    queries_used = usage("queries_made")
    unlimited = user.plan in ("pro", "enterprise")

    return {
        "plan": user.plan,
        "documents": {"total": total_docs, "ready": ready_docs, "chunks": total_chunks},
        "chat": {"sessions": total_sessions, "messages": total_messages},
        "usage": {
            "documents": {
                "used": docs_used,
                "limit": None if unlimited else settings.FREE_DOC_LIMIT,
            },
            "queries": {
                "used": queries_used,
                "limit": None if unlimited else settings.FREE_QUERY_LIMIT,
            },
        },
    }


@router.get("/activity")
def activity(days: int = 14, user: models.User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    """Per-day query counts for a sparkline/bar chart."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        db.query(models.AuditLog.created_at)
        .filter(
            models.AuditLog.user_id == user.id,
            models.AuditLog.action == "chat.query",
            models.AuditLog.created_at >= since,
        )
        .all()
    )
    buckets: dict[str, int] = {}
    for i in range(days):
        d = (datetime.now(timezone.utc) - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        buckets[d] = 0
    for (ts,) in rows:
        key = ts.strftime("%Y-%m-%d")
        if key in buckets:
            buckets[key] += 1
    return {"series": [{"date": k, "queries": v} for k, v in buckets.items()]}
