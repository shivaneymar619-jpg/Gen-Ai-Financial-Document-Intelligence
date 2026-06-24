"""Team workspaces + membership management."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas
from ..deps import get_current_user, record_audit

router = APIRouter(prefix="/teams", tags=["teams"])


@router.post("", response_model=schemas.TeamOut, status_code=201)
def create_team(body: schemas.TeamIn, request: Request,
                user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    team = models.Team(name=body.name, owner_id=user.id)
    db.add(team)
    db.commit()
    db.refresh(team)
    db.add(models.TeamMember(team_id=team.id, user_id=user.id, role="owner"))
    db.commit()
    record_audit(db, user_id=user.id, action="team.create",
                 resource_type="team", resource_id=team.id, ip=request.client.host)
    return team


@router.get("", response_model=list[schemas.TeamOut])
def list_teams(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(models.Team)
        .join(models.TeamMember, models.TeamMember.team_id == models.Team.id)
        .filter(models.TeamMember.user_id == user.id, models.Team.deleted_at.is_(None))
        .all()
    )


@router.get("/{team_id}/members")
def list_members(team_id: str, user: models.User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    _require_member(db, team_id, user)
    rows = (
        db.query(models.User, models.TeamMember.role)
        .join(models.TeamMember, models.TeamMember.user_id == models.User.id)
        .filter(models.TeamMember.team_id == team_id)
        .all()
    )
    return [{"user_id": u.id, "email": u.email, "full_name": u.full_name, "role": role}
            for u, role in rows]


@router.post("/{team_id}/members", status_code=201)
def add_member(team_id: str, body: schemas.MemberIn, request: Request,
               user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_role(db, team_id, user, {"owner", "admin"})
    invitee = db.query(models.User).filter(models.User.email == body.email).first()
    if not invitee:
        raise HTTPException(status_code=404, detail="No user with that email.")
    existing = db.query(models.TeamMember).filter(
        models.TeamMember.team_id == team_id, models.TeamMember.user_id == invitee.id
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Already a member.")
    db.add(models.TeamMember(team_id=team_id, user_id=invitee.id, role=body.role))
    db.commit()
    record_audit(db, user_id=user.id, action="team.add_member",
                 resource_type="team", resource_id=team_id,
                 detail={"member": body.email}, ip=request.client.host)
    return {"status": "added"}


@router.delete("/{team_id}/members/{member_user_id}", status_code=204)
def remove_member(team_id: str, member_user_id: str,
                  user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_role(db, team_id, user, {"owner", "admin"})
    rec = db.query(models.TeamMember).filter(
        models.TeamMember.team_id == team_id, models.TeamMember.user_id == member_user_id
    ).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Member not found.")
    db.delete(rec)
    db.commit()


def _require_member(db, team_id, user) -> models.TeamMember:
    m = db.query(models.TeamMember).filter(
        models.TeamMember.team_id == team_id, models.TeamMember.user_id == user.id
    ).first()
    if not m:
        raise HTTPException(status_code=403, detail="Not a team member.")
    return m


def _require_role(db, team_id, user, roles: set):
    m = _require_member(db, team_id, user)
    if m.role not in roles:
        raise HTTPException(status_code=403, detail="Insufficient team role.")
    return m
