"""Compliance audit trail — searchable + CSV export."""
import csv
import io
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models
from ..deps import get_current_user

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/logs")
def list_logs(
    action: str | None = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = 0,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(models.AuditLog).filter(models.AuditLog.user_id == user.id)
    if action:
        q = q.filter(models.AuditLog.action == action)
    total = q.count()
    rows = q.order_by(models.AuditLog.created_at.desc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "items": [
            {
                "id": r.id, "action": r.action, "resource_type": r.resource_type,
                "resource_id": r.resource_id, "detail": r.detail,
                "ip_address": r.ip_address, "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
    }


@router.get("/logs/export")
def export_logs(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Pro feature in the spec; exposed here for completeness. Returns CSV."""
    rows = (
        db.query(models.AuditLog)
        .filter(models.AuditLog.user_id == user.id)
        .order_by(models.AuditLog.created_at.desc())
        .all()
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["timestamp", "action", "resource_type", "resource_id", "ip_address", "detail"])
    for r in rows:
        writer.writerow([
            r.created_at.isoformat(), r.action, r.resource_type or "",
            r.resource_id or "", r.ip_address or "", str(r.detail or ""),
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_logs.csv"},
    )
