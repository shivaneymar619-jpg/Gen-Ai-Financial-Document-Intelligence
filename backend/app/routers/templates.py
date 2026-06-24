"""Reusable query templates (invoices, bank statements, loan agreements, ...)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_

from ..database import get_db
from .. import models, schemas
from ..deps import get_current_user

router = APIRouter(prefix="/templates", tags=["templates"])

# Ships with sensible defaults the spec calls out.
STARTER_TEMPLATES = [
    {"name": "Invoice Summary", "doc_type": "invoice",
     "queries": ["What is the total amount due?", "What is the invoice date and due date?",
                 "Who is the vendor and what are the line items?"]},
    {"name": "Bank Statement Review", "doc_type": "bank_statement",
     "queries": ["What is the closing balance?", "List the largest transactions.",
                 "Are there any overdraft or fee charges?"]},
    {"name": "Loan Agreement Terms", "doc_type": "loan_agreement",
     "queries": ["What is the interest rate and type?", "What is the repayment schedule?",
                 "What are the covenants and default conditions?"]},
]


@router.get("", response_model=list[schemas.TemplateOut])
def list_templates(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(models.Template).filter(
        or_(models.Template.owner_id == user.id, models.Template.is_public == True)  # noqa: E712
    ).order_by(models.Template.use_count.desc()).all()


@router.post("", response_model=schemas.TemplateOut, status_code=201)
def create_template(body: schemas.TemplateIn, user: models.User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    t = models.Template(
        owner_id=user.id, name=body.name, doc_type=body.doc_type,
        queries=body.queries, is_public=body.is_public,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@router.post("/{template_id}/use", response_model=schemas.TemplateOut)
def use_template(template_id: str, user: models.User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    t = db.query(models.Template).filter(
        models.Template.id == template_id,
        or_(models.Template.owner_id == user.id, models.Template.is_public == True),  # noqa: E712
    ).first()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found.")
    t.use_count += 1
    db.commit()
    db.refresh(t)
    return t


@router.post("/seed", response_model=list[schemas.TemplateOut])
def seed_defaults(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create the starter templates for this user if they have none."""
    existing = db.query(models.Template).filter(models.Template.owner_id == user.id).count()
    if existing:
        return list_templates(user, db)
    for spec in STARTER_TEMPLATES:
        db.add(models.Template(owner_id=user.id, is_public=False, **spec))
    db.commit()
    return db.query(models.Template).filter(
        models.Template.owner_id == user.id
    ).order_by(models.Template.use_count.desc()).all()
