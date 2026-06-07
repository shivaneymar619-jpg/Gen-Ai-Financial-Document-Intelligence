"""RAG chat: multi-turn sessions, citation-grounded answers, freemium-gated queries."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas
from ..config import settings
from ..deps import get_current_user, record_audit, enforce_and_increment
from ..services import rag_service

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/sessions", response_model=schemas.SessionOut, status_code=201)
def create_session(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = models.ChatSession(owner_id=user.id, title="New chat")
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@router.get("/sessions", response_model=list[schemas.SessionOut])
def list_sessions(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(models.ChatSession)
        .filter(models.ChatSession.owner_id == user.id, models.ChatSession.deleted_at.is_(None))
        .order_by(models.ChatSession.created_at.desc())
        .all()
    )


@router.get("/sessions/{session_id}/messages", response_model=list[schemas.MessageOut])
def get_messages(session_id: str, user: models.User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    _owned_session(db, session_id, user)
    return (
        db.query(models.Message)
        .filter(models.Message.session_id == session_id)
        .order_by(models.Message.created_at.asc())
        .all()
    )


@router.post("/ask", response_model=schemas.AnswerOut)
def ask(body: schemas.AskIn, request: Request,
        user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Freemium gate on queries
    enforce_and_increment(db, user, "queries_made", settings.FREE_QUERY_LIMIT)

    # Resolve or create session
    if body.session_id:
        session = _owned_session(db, body.session_id, user)
    else:
        session = models.ChatSession(owner_id=user.id, title=body.question[:48])
        db.add(session)
        db.commit()
        db.refresh(session)

    # Build conversation history for multi-turn context
    history = [
        {"role": m.role, "content": m.content}
        for m in db.query(models.Message)
        .filter(models.Message.session_id == session.id)
        .order_by(models.Message.created_at.asc())
        .all()
    ]

    # Persist user message
    db.add(models.Message(session_id=session.id, role="user", content=body.question))
    db.commit()

    # Run RAG
    answer_text, sources, confidence = rag_service.answer(db, user.id, body.question, history)

    # Persist assistant message
    db.add(models.Message(
        session_id=session.id, role="assistant", content=answer_text,
        sources=sources, confidence=confidence,
    ))
    if session.title == "New chat":
        session.title = body.question[:48]
    db.commit()

    record_audit(db, user_id=user.id, action="chat.query",
                 resource_type="chat_session", resource_id=session.id,
                 detail={"question": body.question[:120]}, ip=request.client.host)

    return schemas.AnswerOut(
        session_id=session.id, answer=answer_text, sources=sources, confidence=confidence
    )


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: str, user: models.User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    from datetime import datetime, timezone
    session = _owned_session(db, session_id, user)
    session.deleted_at = datetime.now(timezone.utc)
    db.commit()


def _owned_session(db: Session, session_id: str, user: models.User) -> models.ChatSession:
    s = db.query(models.ChatSession).filter(
        models.ChatSession.id == session_id,
        models.ChatSession.owner_id == user.id,
        models.ChatSession.deleted_at.is_(None),
    ).first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found.")
    return s
