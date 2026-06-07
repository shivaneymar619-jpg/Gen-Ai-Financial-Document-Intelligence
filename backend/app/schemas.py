"""Pydantic request/response schemas."""
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


# ── Auth ───────────────────────────────────────────────────────────────
class RegisterIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshIn(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    plan: str
    created_at: datetime

    class Config:
        from_attributes = True


# ── Documents ──────────────────────────────────────────────────────────
class DocumentOut(BaseModel):
    id: str
    filename: str
    content_type: str | None = None
    size_bytes: int
    pages: int
    chunk_count: int
    status: str
    error: str | None = None
    created_at: datetime
    processed_at: datetime | None = None

    class Config:
        from_attributes = True


# ── Chat ───────────────────────────────────────────────────────────────
class SessionOut(BaseModel):
    id: str
    title: str
    created_at: datetime

    class Config:
        from_attributes = True


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None


class Source(BaseModel):
    document: str
    page: int
    snippet: str


class AnswerOut(BaseModel):
    session_id: str
    answer: str
    sources: list[Source]
    confidence: float


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    sources: list | None = None
    confidence: float | None = None
    created_at: datetime

    class Config:
        from_attributes = True


# ── Teams ──────────────────────────────────────────────────────────────
class TeamIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class TeamOut(BaseModel):
    id: str
    name: str
    created_at: datetime

    class Config:
        from_attributes = True


class MemberIn(BaseModel):
    email: EmailStr
    role: str = "member"


# ── Templates ──────────────────────────────────────────────────────────
class TemplateIn(BaseModel):
    name: str
    doc_type: str | None = None
    queries: list[str]
    is_public: bool = False


class TemplateOut(BaseModel):
    id: str
    name: str
    doc_type: str | None = None
    queries: list[str]
    is_public: bool
    use_count: int
    created_at: datetime

    class Config:
        from_attributes = True


# ── API keys ───────────────────────────────────────────────────────────
class ApiKeyIn(BaseModel):
    name: str = "default"


class ApiKeyOut(BaseModel):
    id: str
    name: str
    prefix: str
    created_at: datetime
    revoked: bool

    class Config:
        from_attributes = True


class ApiKeyCreatedOut(ApiKeyOut):
    key: str  # full key, shown once
