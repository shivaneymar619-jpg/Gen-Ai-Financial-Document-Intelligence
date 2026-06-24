"""Shared FastAPI dependencies: current-user resolution + audit + usage."""
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .database import get_db
from . import models
from .security import decode_token, hash_api_key
from .config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_PREFIX}/auth/login", auto_error=False)


def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    """Resolve user from a Bearer JWT, or from an `X-API-Key` header."""
    user = None

    api_key = request.headers.get("X-API-Key")
    if api_key:
        hashed = hash_api_key(api_key)
        rec = db.query(models.ApiKey).filter(
            models.ApiKey.hashed_key == hashed, models.ApiKey.revoked == False  # noqa: E712
        ).first()
        if rec:
            rec.last_used_at = datetime.now(timezone.utc)
            db.commit()
            user = db.query(models.User).filter(models.User.id == rec.user_id).first()

    if user is None and token:
        payload = decode_token(token)
        if payload and payload.get("type") == "access" and payload.get("sub") is not None:
            user = db.query(models.User).filter(models.User.id == payload["sub"]).first()

    if user is None or user.deleted_at is not None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def current_period() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def record_audit(db: Session, *, user_id: str | None, action: str,
                 resource_type: str = None, resource_id: str = None,
                 detail: dict = None, ip: str = None):
    """Append an immutable audit entry."""
    log = models.AuditLog(
        user_id=user_id, action=action, resource_type=resource_type,
        resource_id=resource_id, detail=detail, ip_address=ip,
    )
    db.add(log)
    db.commit()


def get_usage(db: Session, user_id: str, metric: str) -> models.UsageMetric:
    period = current_period()
    rec = db.query(models.UsageMetric).filter(
        models.UsageMetric.user_id == user_id,
        models.UsageMetric.metric == metric,
        models.UsageMetric.period == period,
    ).first()
    if not rec:
        rec = models.UsageMetric(user_id=user_id, metric=metric, value=0, period=period)
        db.add(rec)
        db.commit()
        db.refresh(rec)
    return rec


def enforce_and_increment(db: Session, user: models.User, metric: str, limit: int):
    """Freemium gate. Pro/enterprise are unlimited."""
    if user.plan in ("pro", "enterprise"):
        rec = get_usage(db, user.id, metric)
        rec.value += 1
        db.commit()
        return
    rec = get_usage(db, user.id, metric)
    if rec.value >= limit:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Free plan limit reached for {metric} ({limit}/month). Upgrade to Pro for unlimited.",
        )
    rec.value += 1
    db.commit()
