"""Document management: upload (async processing), list, get, soft-delete, restore, batch."""
import os
import uuid
from datetime import datetime, timezone

from fastapi import (
    APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, Request
)
from sqlalchemy.orm import Session

from ..database import get_db, SessionLocal
from .. import models, schemas
from ..config import settings
from ..deps import get_current_user, record_audit, enforce_and_increment
from ..services.document_service import process_document

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".txt", ".md", ".csv"}


def _process_in_background(document_id: str):
    """Runs in a FastAPI BackgroundTask with its own DB session
    (stand-in for the Celery worker described in the spec)."""
    db = SessionLocal()
    try:
        process_document(db, document_id)
    finally:
        db.close()


@router.post("/upload", response_model=list[schemas.DocumentOut], status_code=201)
async def upload(
    request: Request,
    background: BackgroundTasks,
    files: list[UploadFile] = File(...),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Batch upload. Each file is saved, recorded, and queued for async processing."""
    created: list[models.Document] = []
    for f in files:
        if not f.filename:
            raise HTTPException(status_code=422, detail="Each file must have a filename.")
        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in ALLOWED:
            raise HTTPException(status_code=415, detail=f"Unsupported file type: {ext}")

        data = await f.read()
        stored_name = f"{uuid.uuid4().hex}{ext}"
        path = settings.STORAGE_DIR / stored_name
        with open(path, "wb") as out:
            out.write(data)

        # Freemium gate — checked after the file is safely on disk so a quota
        # error doesn't consume the slot for a write that never happened.
        enforce_and_increment(db, user, "documents_uploaded", settings.FREE_DOC_LIMIT)

        doc = models.Document(
            owner_id=user.id, filename=f.filename, content_type=f.content_type,
            size_bytes=len(data), status="pending", storage_path=str(path),
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        created.append(doc)

        record_audit(db, user_id=user.id, action="document.upload",
                     resource_type="document", resource_id=doc.id,
                     detail={"filename": f.filename, "size": len(data)},
                     ip=request.client.host)
        background.add_task(_process_in_background, doc.id)

    return created


@router.get("", response_model=list[schemas.DocumentOut])
def list_documents(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(models.Document)
        .filter(models.Document.owner_id == user.id, models.Document.deleted_at.is_(None))
        .order_by(models.Document.created_at.desc())
        .all()
    )


@router.get("/{doc_id}", response_model=schemas.DocumentOut)
def get_document(doc_id: str, user: models.User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    doc = _owned(db, doc_id, user)
    return doc


@router.delete("/{doc_id}", status_code=204)
def delete_document(doc_id: str, request: Request,
                    user: models.User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    """Soft delete."""
    doc = _owned(db, doc_id, user)
    doc.deleted_at = datetime.now(timezone.utc)
    db.commit()
    record_audit(db, user_id=user.id, action="document.delete",
                 resource_type="document", resource_id=doc.id, ip=request.client.host)


@router.post("/{doc_id}/restore", response_model=schemas.DocumentOut)
def restore_document(doc_id: str, user: models.User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    doc = db.query(models.Document).filter(
        models.Document.id == doc_id, models.Document.owner_id == user.id
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    doc.deleted_at = None
    db.commit()
    db.refresh(doc)
    return doc


@router.post("/{doc_id}/reprocess", response_model=schemas.DocumentOut)
def reprocess(doc_id: str, background: BackgroundTasks,
              user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = _owned(db, doc_id, user)
    doc.status = "pending"
    db.commit()
    db.refresh(doc)
    background.add_task(_process_in_background, doc.id)
    return doc


def _owned(db: Session, doc_id: str, user: models.User) -> models.Document:
    doc = db.query(models.Document).filter(
        models.Document.id == doc_id,
        models.Document.owner_id == user.id,
        models.Document.deleted_at.is_(None),
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return doc
