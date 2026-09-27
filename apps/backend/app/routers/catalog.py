import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import get_current_user, require
from app.models import Camera, Factory, Incident, IncidentEvidence, OperatorFeedback, Rule, User, Zone, AIModel
from app.schemas import CameraIn, CameraOut, CameraUpdate, FactoryOut, ModelOut, RuleIn, RuleOut, RuleUpdate, ZoneIn, ZoneOut
from app.services import camera_out, read_live, rule_out
from app.storage import get_bytes, put_bytes
from app.validators import CONDITION_TYPES, EVENT_TYPES, SEVERITIES, STREAM_TYPES, ZONE_TYPES, validate_polygon

router = APIRouter(prefix="/api", tags=["configuration"])


def _factory(db: Session, factory_id: str | None) -> Factory:
    factory = db.get(Factory, factory_id) if factory_id else db.query(Factory).first()
    if factory is None:
        raise HTTPException(status_code=400, detail="Create a factory before adding a camera")
    return factory


def _check(value: str, allowed: set[str], label: str) -> None:
    if value not in allowed:
        raise HTTPException(status_code=400, detail=f"Unknown {label}")


@router.get("/factories", response_model=list[FactoryOut])
def list_factories(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Factory).order_by(Factory.name).all()


@router.get("/cameras", response_model=list[CameraOut])
def list_cameras(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    cameras = db.query(Camera).order_by(Camera.code).all()
    return [camera_out(camera) for camera in cameras]


@router.post("/cameras", response_model=CameraOut)
def create_camera(body: CameraIn, db: Session = Depends(get_db), _: User = Depends(require("ADMIN"))):
    _check(body.stream_type, STREAM_TYPES, "stream type")
    if db.query(Camera).filter(Camera.code == body.code).first():
        raise HTTPException(status_code=409, detail="A camera with this code already exists")
    factory = _factory(db, body.factory_id)
    camera = Camera(
        factory_id=factory.id,
        code=body.code.strip(),
        name=body.name.strip(),
        area=body.area.strip(),
        stream_type=body.stream_type,
        stream_url=body.stream_url or "",
        enabled=body.enabled,
        ai_fps=body.ai_fps,
        assigned_worker=body.assigned_worker or None,
    )
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return camera_out(camera)


@router.get("/cameras/{camera_id}", response_model=CameraOut)
def get_camera(camera_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    return camera_out(camera)


@router.patch("/cameras/{camera_id}", response_model=CameraOut)
def update_camera(camera_id: str, body: CameraUpdate, db: Session = Depends(get_db), _: User = Depends(require("ADMIN"))):
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    data = body.model_dump(exclude_unset=True)
    if "stream_type" in data and data["stream_type"] is not None:
        _check(data["stream_type"], STREAM_TYPES, "stream type")
    if "stream_url" in data and data["stream_url"] and "***" in data["stream_url"]:
        data.pop("stream_url")
    for field, value in data.items():
        setattr(camera, field, value)
    db.commit()
    db.refresh(camera)
    return camera_out(camera)


@router.delete("/cameras/{camera_id}")
def delete_camera(camera_id: str, db: Session = Depends(get_db), _: User = Depends(require("ADMIN"))):
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    incident_ids = [row[0] for row in db.query(Incident.id).filter(Incident.camera_id == camera.id).all()]
    if incident_ids:
        db.query(OperatorFeedback).filter(OperatorFeedback.incident_id.in_(incident_ids)).delete(synchronize_session=False)
        db.query(IncidentEvidence).filter(IncidentEvidence.incident_id.in_(incident_ids)).delete(synchronize_session=False)
        db.query(Incident).filter(Incident.id.in_(incident_ids)).delete(synchronize_session=False)
    db.query(Rule).filter(Rule.camera_id == camera.id).delete(synchronize_session=False)
    db.query(Zone).filter(Zone.camera_id == camera.id).delete(synchronize_session=False)
    db.delete(camera)
    db.commit()
    return {"deleted": True}


@router.post("/cameras/{camera_id}/video", response_model=CameraOut)
async def upload_video(
    camera_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require("ADMIN")),
):
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    filename = (file.filename or "").lower()
    if not filename.endswith(".mp4"):
        raise HTTPException(status_code=400, detail="Upload an MP4 video")
    data = await file.read()
    if len(data) > 200 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Video must be 200 MB or smaller")
    key = f"videos/{camera.id}/{uuid.uuid4().hex}.mp4"
    try:
        put_bytes(key, data, "video/mp4")
    except Exception:
        raise HTTPException(status_code=503, detail="Video storage is unavailable")
    camera.stream_type = "FILE"
    camera.stream_url = key
    db.commit()
    db.refresh(camera)
    return camera_out(camera)


@router.get("/cameras/{camera_id}/snapshot")
def camera_snapshot(camera_id: str, raw: bool = False, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    key = f"cameras/{camera.id}/{'latest_raw' if raw else 'latest'}.jpg"
    data = get_bytes(key)
    if data is None:
        raise HTTPException(status_code=404, detail="No frame yet. The camera worker is still starting.")
    return Response(content=data, media_type="image/jpeg")


@router.get("/cameras/{camera_id}/live")
def camera_live(camera_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    live = read_live(camera.id) or {}
    return {
        "camera_id": camera.id,
        "status": camera_out(camera, live).status,
        "ai_mode": live.get("ai_mode"),
        "ai_fps": live.get("ai_fps"),
        "inference_ms": live.get("inference_ms"),
        "frames_processed": live.get("frames_processed"),
        "dropped_frames": live.get("dropped_frames"),
        "source_state": live.get("source_state"),
        "tracks": live.get("tracks") or [],
    }


@router.post("/cameras/{camera_id}/simulate")
def simulate(camera_id: str, db: Session = Depends(get_db), _: User = Depends(require("ADMIN", "SAFETY_MANAGER"))):
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    camera.simulate_pending = True
    db.commit()
    return {"queued": True, "camera_id": camera.id}


@router.get("/zones", response_model=list[ZoneOut])
def list_zones(camera_id: str | None = None, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    query = db.query(Zone)
    if camera_id:
        query = query.filter(Zone.camera_id == camera_id)
    return query.order_by(Zone.name).all()


@router.post("/zones", response_model=ZoneOut)
def create_zone(body: ZoneIn, db: Session = Depends(get_db), _: User = Depends(require("ADMIN"))):
    _check(body.zone_type, ZONE_TYPES, "zone type")
    camera = db.get(Camera, body.camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    try:
        polygon = validate_polygon(body.polygon)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    zone = Zone(factory_id=camera.factory_id, camera_id=camera.id, name=body.name.strip(), zone_type=body.zone_type, polygon=polygon)
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return zone


@router.delete("/zones/{zone_id}")
def delete_zone(zone_id: str, db: Session = Depends(get_db), _: User = Depends(require("ADMIN"))):
    zone = db.get(Zone, zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail="Zone not found")
    db.query(Incident).filter(Incident.zone_id == zone.id).update({Incident.zone_id: None, Incident.rule_id: None}, synchronize_session=False)
    db.query(Rule).filter(Rule.zone_id == zone.id).delete(synchronize_session=False)
    db.delete(zone)
    db.commit()
    return {"deleted": True}


@router.get("/rules", response_model=list[RuleOut])
def list_rules(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rules = db.query(Rule).options(joinedload(Rule.zone), joinedload(Rule.camera)).order_by(Rule.name).all()
    return [rule_out(rule) for rule in rules]


@router.post("/rules", response_model=RuleOut)
def create_rule(body: RuleIn, db: Session = Depends(get_db), _: User = Depends(require("ADMIN"))):
    _check(body.event_type, EVENT_TYPES, "event type")
    _check(body.condition_type, CONDITION_TYPES, "condition")
    _check(body.severity, SEVERITIES, "severity")
    zone = db.query(Zone).options(joinedload(Zone.camera)).filter(Zone.id == body.zone_id).first()
    if zone is None:
        raise HTTPException(status_code=404, detail="Zone not found")
    rule = Rule(
        factory_id=zone.factory_id,
        camera_id=zone.camera_id,
        zone_id=zone.id,
        name=body.name.strip(),
        event_type=body.event_type,
        condition_type=body.condition_type,
        min_duration_ms=body.min_duration_ms,
        cooldown_ms=body.cooldown_ms,
        grace_ms=body.grace_ms,
        severity=body.severity,
        enabled=body.enabled,
        extensions={},
    )
    db.add(rule)
    db.commit()
    rule = db.query(Rule).options(joinedload(Rule.zone), joinedload(Rule.camera)).filter(Rule.id == rule.id).one()
    return rule_out(rule)


@router.patch("/rules/{rule_id}", response_model=RuleOut)
def update_rule(rule_id: str, body: RuleUpdate, db: Session = Depends(get_db), _: User = Depends(require("ADMIN"))):
    rule = db.query(Rule).options(joinedload(Rule.zone), joinedload(Rule.camera)).filter(Rule.id == rule_id).first()
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    data = body.model_dump(exclude_unset=True)
    if "event_type" in data and data["event_type"] is not None:
        _check(data["event_type"], EVENT_TYPES, "event type")
    if "condition_type" in data and data["condition_type"] is not None:
        _check(data["condition_type"], CONDITION_TYPES, "condition")
    if "severity" in data and data["severity"] is not None:
        _check(data["severity"], SEVERITIES, "severity")
    for field, value in data.items():
        setattr(rule, field, value)
    db.commit()
    db.refresh(rule)
    return rule_out(rule)


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: str, db: Session = Depends(get_db), _: User = Depends(require("ADMIN"))):
    rule = db.get(Rule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.query(Incident).filter(Incident.rule_id == rule.id).update({Incident.rule_id: None}, synchronize_session=False)
    db.delete(rule)
    db.commit()
    return {"deleted": True}


@router.get("/models", response_model=list[ModelOut])
def list_models(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(AIModel).order_by(AIModel.name).all()
