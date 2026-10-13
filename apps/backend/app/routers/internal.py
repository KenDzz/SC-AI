import hmac

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Camera, Rule, Zone
from app.schemas import HeartbeatIn, IncidentClose, IncidentCreate
from app.services import close_incident, create_worker_incident, incident_out, write_live

router = APIRouter(prefix="/api/internal", tags=["internal"])


def require_worker(x_internal_token: str = Header(default="")):
    expected = get_settings().internal_api_token
    if not hmac.compare_digest(x_internal_token, expected):
        raise HTTPException(status_code=401, detail="Worker token is invalid")


@router.get("/cameras")
def list_cameras(db: Session = Depends(get_db), _: None = Depends(require_worker)):
    cameras = db.query(Camera).all()
    payload = []
    for camera in cameras:
        zones = db.query(Zone).filter(Zone.camera_id == camera.id).all()
        rules = db.query(Rule).filter(Rule.camera_id == camera.id, Rule.enabled.is_(True)).all()
        payload.append(
            {
                "id": camera.id,
                "factory_id": camera.factory_id,
                "code": camera.code,
                "name": camera.name,
                "area": camera.area,
                "stream_type": camera.stream_type,
                "stream_url": camera.stream_url or "",
                "enabled": camera.enabled,
                "ai_fps": camera.ai_fps,
                "assigned_worker": camera.assigned_worker,
                "simulate_pending": camera.simulate_pending,
                "multi_view": bool(camera.multi_view),
                "zones": [
                    {"id": zone.id, "name": zone.name, "zone_type": zone.zone_type, "polygon": zone.polygon, "reference_key": zone.reference_key}
                    for zone in zones
                ],
                "rules": [
                    {
                        "id": rule.id,
                        "zone_id": rule.zone_id,
                        "name": rule.name,
                        "event_type": rule.event_type,
                        "condition_type": rule.condition_type,
                        "min_duration_ms": rule.min_duration_ms,
                        "cooldown_ms": rule.cooldown_ms,
                        "grace_ms": rule.grace_ms,
                        "severity": rule.severity,
                        "enabled": rule.enabled,
                    }
                    for rule in rules
                ],
            }
        )
    return payload


@router.post("/cameras/{camera_id}/heartbeat")
def heartbeat(camera_id: str, body: HeartbeatIn, db: Session = Depends(get_db), _: None = Depends(require_worker)):
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    write_live(camera_id, body.model_dump())
    return {"stored": True}


@router.post("/cameras/{camera_id}/simulate-ack")
def ack_simulate(camera_id: str, db: Session = Depends(get_db), _: None = Depends(require_worker)):
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    camera.simulate_pending = False
    db.commit()
    return {"acked": True}


@router.post("/incidents")
def open_incident(body: IncidentCreate, db: Session = Depends(get_db), _: None = Depends(require_worker)):
    incident, reason = create_worker_incident(db, body)
    return {"id": incident.id, "reason": reason, "incident": incident_out(incident).model_dump(mode="json")}


@router.post("/incidents/{incident_id}/close")
def close(incident_id: str, body: IncidentClose, db: Session = Depends(get_db), _: None = Depends(require_worker)):
    incident = close_incident(db, incident_id, body.ended_at)
    return incident_out(incident).model_dump(mode="json")
