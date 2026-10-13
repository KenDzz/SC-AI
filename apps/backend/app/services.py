import base64
import json
import logging
import time
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Incident, IncidentEvidence, OperatorFeedback
from app.redis_client import get_redis, publish
from app.schemas import CameraOut, FeedbackOut, IncidentOut, RuleOut
from app.storage import put_bytes
from app.timeutils import ensure_utc
from app.mask import mask_stream_url
from app.validators import REVIEW_TRANSITIONS

log = logging.getLogger("api.services")


def write_live(camera_id: str, payload: dict) -> None:
    client = get_redis()
    if client is None:
        return
    body = dict(payload)
    body["received_at"] = time.time()
    try:
        client.setex(f"live:{camera_id}", 30, json.dumps(body))
        client.set("worker:ai_mode", body.get("ai_mode") or "")
    except Exception:
        log.warning("live state was not stored")


def read_live(camera_id: str) -> dict | None:
    client = get_redis()
    if client is None:
        return None
    try:
        raw = client.get(f"live:{camera_id}")
    except Exception:
        return None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def read_lives() -> list[dict]:
    client = get_redis()
    if client is None:
        return []
    lives = []
    try:
        for key in client.scan_iter("live:*"):
            raw = client.get(key)
            if raw:
                lives.append(json.loads(raw))
    except Exception:
        return lives
    return lives


def display_status(camera, live: dict | None) -> str:
    if not camera.enabled:
        return "DISABLED"
    if not live:
        return "OFFLINE"
    age = time.time() - float(live.get("received_at") or 0)
    if age > 15:
        return "OFFLINE"
    return live.get("status") or "OFFLINE"


def camera_out(camera, live: dict | None = None) -> CameraOut:
    if live is None:
        live = read_live(camera.id)
    return CameraOut(
        id=camera.id,
        factory_id=camera.factory_id,
        code=camera.code,
        name=camera.name,
        area=camera.area,
        stream_type=camera.stream_type,
        stream_url=mask_stream_url(camera.stream_url),
        enabled=camera.enabled,
        ai_fps=camera.ai_fps,
        assigned_worker=camera.assigned_worker,
        multi_view=bool(camera.multi_view),
        status=display_status(camera, live),
        created_at=camera.created_at,
        updated_at=camera.updated_at,
    )


def rule_out(rule) -> RuleOut:
    return RuleOut(
        id=rule.id,
        factory_id=rule.factory_id,
        camera_id=rule.camera_id,
        zone_id=rule.zone_id,
        zone_name=rule.zone.name if rule.zone else None,
        camera_name=rule.camera.name if rule.camera else None,
        name=rule.name,
        event_type=rule.event_type,
        condition_type=rule.condition_type,
        min_duration_ms=rule.min_duration_ms,
        cooldown_ms=rule.cooldown_ms,
        grace_ms=rule.grace_ms,
        severity=rule.severity,
        enabled=rule.enabled,
        extensions=rule.extensions or {},
    )


def incident_out(incident: Incident) -> IncidentOut:
    return IncidentOut(
        id=incident.id,
        factory_id=incident.factory_id,
        camera_id=incident.camera_id,
        camera_name=incident.camera.name if incident.camera else None,
        zone_id=incident.zone_id,
        zone_name=incident.zone.name if incident.zone else None,
        rule_id=incident.rule_id,
        rule_name=incident.rule.name if incident.rule else None,
        event_type=incident.event_type,
        severity=incident.severity,
        track_id=incident.track_id,
        confidence=incident.confidence,
        started_at=incident.started_at,
        ended_at=incident.ended_at,
        status=incident.status,
        snapshot_uri=incident.snapshot_uri,
        clip_uri=incident.clip_uri,
        model_name=incident.model_name,
        model_version=incident.model_version,
        ai_mode=incident.ai_mode,
        created_at=incident.created_at,
        updated_at=incident.updated_at,
    )


def feedback_out(row: OperatorFeedback) -> FeedbackOut:
    return FeedbackOut(
        id=row.id,
        decision=row.decision,
        comment=row.comment,
        user_name=row.user.full_name if row.user else "Operator",
        created_at=row.created_at,
    )


def notify(incident: Incident) -> None:
    publish("incidents", json.dumps({"type": "incident", "incident": incident_out(incident).model_dump(mode="json")}))


def create_worker_incident(db: Session, body) -> tuple[Incident, str]:
    from app.models import Rule

    rule = db.get(Rule, body.rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    cooldown = timedelta(milliseconds=rule.cooldown_ms or 0)
    recent = (
        db.query(Incident)
        .filter(Incident.camera_id == body.camera_id, Incident.rule_id == body.rule_id, Incident.track_id == body.track_id)
        .order_by(Incident.created_at.desc())
        .first()
    )
    now = datetime.now(timezone.utc)
    if recent is not None and recent.ended_at is None:
        return _reload(db, recent.id), "duplicate_open"
    if recent is not None and recent.ended_at is not None and now - ensure_utc(recent.ended_at) < cooldown:
        return _reload(db, recent.id), "cooldown"
    incident = Incident(
        factory_id=body.factory_id,
        camera_id=body.camera_id,
        zone_id=body.zone_id,
        rule_id=body.rule_id,
        event_type=body.event_type,
        severity=body.severity,
        track_id=body.track_id,
        confidence=body.confidence,
        started_at=ensure_utc(body.started_at),
        status="NEW",
        model_name=body.model_name,
        model_version=body.model_version,
        ai_mode=body.ai_mode,
    )
    db.add(incident)
    db.flush()
    _attach_image(db, incident, body.snapshot_base64, "snapshot", "snapshot.jpg")
    _attach_image(db, incident, body.crop_base64, "person_crop", "crop.jpg")
    db.commit()
    loaded = _reload(db, incident.id)
    notify(loaded)
    return loaded, "created"


def close_incident(db: Session, incident_id: str, ended_at: datetime) -> Incident:
    incident = _reload(db, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    incident.ended_at = ensure_utc(ended_at)
    incident.updated_at = datetime.now(timezone.utc)
    db.commit()
    loaded = _reload(db, incident.id)
    notify(loaded)
    return loaded


def review_incident(db: Session, incident: Incident, user, decision: str, comment: str) -> Incident:
    allowed = REVIEW_TRANSITIONS.get(incident.status, set())
    if decision not in allowed:
        raise HTTPException(status_code=409, detail=f"This incident is already {incident.status}")
    incident.status = decision
    incident.updated_at = datetime.now(timezone.utc)
    db.add(OperatorFeedback(incident_id=incident.id, decision=decision, comment=comment or "", user_id=user.id))
    db.commit()
    loaded = _reload(db, incident.id)
    notify(loaded)
    return loaded


def _attach_image(db: Session, incident: Incident, encoded: str | None, kind: str, filename: str) -> None:
    if not encoded:
        return
    try:
        data = base64.b64decode(encoded)
    except Exception:
        log.warning("evidence payload could not be decoded", extra={"incident_id": incident.id})
        return
    key = f"incidents/{incident.id}/{filename}"
    try:
        put_bytes(key, data, "image/jpeg")
    except Exception:
        log.warning("evidence upload failed", extra={"incident_id": incident.id})
        return
    if kind == "snapshot":
        incident.snapshot_uri = key
    db.add(IncidentEvidence(incident_id=incident.id, kind=kind, object_key=key))


def _reload(db: Session, incident_id: str) -> Incident | None:
    statement = (
        select(Incident)
        .options(joinedload(Incident.camera), joinedload(Incident.zone), joinedload(Incident.rule), joinedload(Incident.feedback).joinedload(OperatorFeedback.user))
        .where(Incident.id == incident_id)
    )
    return db.scalars(statement).unique().first()
