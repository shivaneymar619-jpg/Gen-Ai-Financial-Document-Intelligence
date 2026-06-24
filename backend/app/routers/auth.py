"""Authentication: register, login, refresh, current user, API keys."""
import re
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas
from ..security import (
    hash_password, verify_password, create_token, decode_token,
    generate_api_key,
)
from ..deps import get_current_user, record_audit

router = APIRouter(prefix="/auth", tags=["auth"])

PASSWORD_RE = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$")


@router.post("/register", response_model=schemas.TokenOut, status_code=201)
def register(body: schemas.RegisterIn, request: Request, db: Session = Depends(get_db)):
    if not PASSWORD_RE.match(body.password):
        raise HTTPException(
            status_code=422,
            detail="Password must be 8+ chars and include upper, lower, and a digit.",
        )
    existing = db.query(models.User).filter(models.User.email == body.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered.")

    user = models.User(
        email=body.email, full_name=body.full_name,
        hashed_password=hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    record_audit(db, user_id=user.id, action="auth.register",
                 resource_type="user", resource_id=user.id, ip=request.client.host)
    return schemas.TokenOut(
        access_token=create_token(user.id, "access"),
        refresh_token=create_token(user.id, "refresh"),
    )


@router.post("/login", response_model=schemas.TokenOut)
def login(body: schemas.LoginIn, request: Request, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == body.email).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if user.deleted_at is not None or not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled.")
    record_audit(db, user_id=user.id, action="auth.login",
                 resource_type="user", resource_id=user.id, ip=request.client.host)
    return schemas.TokenOut(
        access_token=create_token(user.id, "access"),
        refresh_token=create_token(user.id, "refresh"),
    )


@router.post("/refresh", response_model=schemas.TokenOut)
def refresh(body: schemas.RefreshIn, db: Session = Depends(get_db)):
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token.")
    user = db.query(models.User).filter(models.User.id == payload["sub"]).first()
    if not user or user.deleted_at is not None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or account disabled.")
    return schemas.TokenOut(
        access_token=create_token(user.id, "access"),
        refresh_token=create_token(user.id, "refresh"),
    )


@router.get("/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(get_current_user)):
    return user


# ── API keys ───────────────────────────────────────────────────────────
@router.post("/api-keys", response_model=schemas.ApiKeyCreatedOut, status_code=201)
def create_api_key(body: schemas.ApiKeyIn, request: Request,
                   user: models.User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    full, prefix, hashed = generate_api_key()
    rec = models.ApiKey(user_id=user.id, name=body.name, prefix=prefix, hashed_key=hashed)
    db.add(rec)
    db.commit()
    db.refresh(rec)
    record_audit(db, user_id=user.id, action="apikey.create",
                 resource_type="api_key", resource_id=rec.id, ip=request.client.host)
    return schemas.ApiKeyCreatedOut(
        id=rec.id, name=rec.name, prefix=rec.prefix,
        created_at=rec.created_at, revoked=rec.revoked, key=full,
    )


@router.get("/api-keys", response_model=list[schemas.ApiKeyOut])
def list_api_keys(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(models.ApiKey).filter(models.ApiKey.user_id == user.id).all()


@router.delete("/api-keys/{key_id}", status_code=204)
def revoke_api_key(key_id: str, user: models.User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    rec = db.query(models.ApiKey).filter(
        models.ApiKey.id == key_id, models.ApiKey.user_id == user.id
    ).first()
    if not rec:
        raise HTTPException(status_code=404, detail="API key not found.")
    rec.revoked = True
    db.commit()
