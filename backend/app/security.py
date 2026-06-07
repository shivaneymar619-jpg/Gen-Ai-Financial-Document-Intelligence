"""Password hashing, JWT tokens, and API-key helpers."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt, JWTError

from .config import settings


# ── Passwords ──────────────────────────────────────────────────────────
# bcrypt operates on the first 72 bytes; we truncate explicitly to avoid
# the "password cannot be longer than 72 bytes" error on long inputs.
def _pw_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:72]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_pw_bytes(password), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_pw_bytes(plain), hashed.encode("utf-8"))
    except Exception:
        return False


# ── JWT ────────────────────────────────────────────────────────────────
def create_token(subject: str, kind: str = "access") -> str:
    now = datetime.now(timezone.utc)
    if kind == "refresh":
        expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": subject, "type": kind, "exp": expire, "iat": now}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


# ── API keys ───────────────────────────────────────────────────────────
def generate_api_key() -> tuple[str, str, str]:
    """Returns (full_key, prefix, hashed_key). Full key shown once to the user."""
    raw = secrets.token_urlsafe(32)
    full = f"fdai_{raw}"
    prefix = full[:12]
    hashed = hashlib.sha256(full.encode()).hexdigest()
    return full, prefix, hashed


def hash_api_key(full: str) -> str:
    return hashlib.sha256(full.encode()).hexdigest()
