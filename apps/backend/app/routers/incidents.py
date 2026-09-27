from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import get_current_user, require
from app.models import Incident, OperatorFeedback, User
from app.schemas import FeedbackOut, IncidentOut, IncidentPage, ReviewIn
from app.services import feedback_out, incident_out, review_incident
from app.storage import get_bytes
from app.timeutils import day_bounds

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


def _query(db: Session, on_date: str | None, camera_id: str | None, zone_id: str | None, event_type: str | None, severity: str | None, status: str | None):
    query = db.query(Incident)
    if on_date:
        start, end = day_bounds(on_date)
        query = query.filter(Incident.started_at >= start, Incident.started_at < end)
    if camera_id:
        query = query.filter(Incident.camera_id == camera_id)
    if zone_id:
        query = query.filter(Incident.zone_id == zone_id)
    if event_type:
        query = query.filter(Incident.event_type == event_type)
    if severity:
        query = query.filter(Incident.severity == severity)
    if status:
        query = query.filter(Incident.status == status)
    return query


def _load(db: Session, incident_id: str) -> Incident:
    statement = (
        select(Incident)
        .options(joinedload(Incident.camera), joinedload(Incident.zone), joinedload(Incident.rule), joinedload(Incident.feedback).joinedload(OperatorFeedback.user))
        .where(Incident.id == incident_id)
    )
    incident = db.scalars(statement).unique().first()
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.get("", response_model=IncidentPage)
def list_incidents(
    on_date: str | None = None,
    camera_id: str | None = None,
    zone_id: str | None = None,
    event_type: str | None = None,
    severity: str | None = None,
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    base = _query(db, on_date, camera_id, zone_id, event_type, severity, status)
    total = base.count()
    rows = (
        base.options(joinedload(Incident.camera), joinedload(Incident.zone), joinedload(Incident.rule))
        .order_by(Incident.started_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return IncidentPage(items=[incident_out(row) for row in rows], total=total)


@router.get("/{incident_id}", response_model=IncidentOut)
def get_incident(incident_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return incident_out(_load(db, incident_id))


@router.get("/{incident_id}/feedback", response_model=list[FeedbackOut])
def list_feedback(incident_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    incident = _load(db, incident_id)
    return [feedback_out(row) for row in sorted(incident.feedback, key=lambda item: item.created_at)]


@router.get("/{incident_id}/snapshot")
def snapshot(incident_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    incident = _load(db, incident_id)
    if not incident.snapshot_uri:
        raise HTTPException(status_code=404, detail="No snapshot for this incident")
    data = get_bytes(incident.snapshot_uri)
    if data is None:
        raise HTTPException(status_code=404, detail="Snapshot file is missing")
    return Response(content=data, media_type="image/jpeg")


def _decide(incident_id: str, decision: str, body: ReviewIn, db: Session, user: User) -> IncidentOut:
    incident = _load(db, incident_id)
    return incident_out(review_incident(db, incident, user, decision, body.comment))


@router.post("/{incident_id}/confirm", response_model=IncidentOut)
def confirm_incident(incident_id: str, body: ReviewIn, db: Session = Depends(get_db), user: User = Depends(require("ADMIN", "SAFETY_MANAGER"))):
    return _decide(incident_id, "CONFIRMED", body, db, user)


@router.post("/{incident_id}/false-positive", response_model=IncidentOut)
def false_positive_incident(incident_id: str, body: ReviewIn, db: Session = Depends(get_db), user: User = Depends(require("ADMIN", "SAFETY_MANAGER"))):
    return _decide(incident_id, "FALSE_POSITIVE", body, db, user)


@router.post("/{incident_id}/resolve", response_model=IncidentOut)
def resolve_incident(incident_id: str, body: ReviewIn, db: Session = Depends(get_db), user: User = Depends(require("ADMIN", "SAFETY_MANAGER"))):
    return _decide(incident_id, "RESOLVED", body, db, user)
