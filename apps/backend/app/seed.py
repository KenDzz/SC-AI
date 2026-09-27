from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AIModel, AIModelDeployment, Camera, Factory, Incident, OperatorFeedback, Rule, User, Zone
from app.security import hash_password

PACKING = [[0.40, 0.20], [0.90, 0.18], [0.92, 0.85], [0.38, 0.88]]
PRODUCTION = [[0.15, 0.22], [0.72, 0.20], [0.76, 0.82], [0.12, 0.84]]
MACHINE = [[0.42, 0.28], [0.82, 0.26], [0.86, 0.78], [0.40, 0.80]]
RESTRICTED = [[0.48, 0.12], [0.92, 0.10], [0.94, 0.62], [0.46, 0.66]]
FORKLIFT = [[0.08, 0.58], [0.88, 0.56], [0.90, 0.96], [0.06, 0.98]]


def seed(db: Session) -> None:
    if db.query(Factory).filter(Factory.code == "coffee-poc").first():
        return
    settings = get_settings()
    factory = Factory(name="Coffee Factory POC", code="coffee-poc", timezone="Asia/Ho_Chi_Minh")
    db.add(factory)
    db.flush()

    users = {
        "admin": User(username="admin", full_name="Factory Admin", role="ADMIN", password_hash=hash_password(settings.demo_admin_password)),
        "safety": User(username="safety", full_name="Safety Manager", role="SAFETY_MANAGER", password_hash=hash_password(settings.demo_safety_password)),
        "viewer": User(username="viewer", full_name="Shift Viewer", role="VIEWER", password_hash=hash_password(settings.demo_viewer_password)),
    }
    db.add_all(users.values())

    cameras = {
        "pack": Camera(factory_id=factory.id, code="CAM-PACK-01", name="Packing Area Camera 01", area="Packing Area", stream_type="FILE", stream_url="", enabled=True, ai_fps=25),
        "prod": Camera(factory_id=factory.id, code="CAM-PROD-01", name="Production Area Camera 01", area="Production Area", stream_type="FILE", stream_url="", enabled=True, ai_fps=25),
        "machine": Camera(factory_id=factory.id, code="CAM-MACHINE-01", name="Machine Area Camera 01", area="Machine Area", stream_type="FILE", stream_url="", enabled=True, ai_fps=25),
        "warehouse": Camera(factory_id=factory.id, code="CAM-WAREHOUSE-01", name="Warehouse Camera 01", area="Warehouse", stream_type="FILE", stream_url="", enabled=True, ai_fps=25),
    }
    db.add_all(cameras.values())
    db.flush()

    zones = {
        "packing": Zone(factory_id=factory.id, camera_id=cameras["pack"].id, name="Packing Zone A", zone_type="PACKING_ZONE", polygon=PACKING),
        "production": Zone(factory_id=factory.id, camera_id=cameras["prod"].id, name="Production Zone A", zone_type="PRODUCTION_ZONE", polygon=PRODUCTION),
        "machine": Zone(factory_id=factory.id, camera_id=cameras["machine"].id, name="Machine A Danger Zone", zone_type="MACHINE_DANGER_ZONE", polygon=MACHINE),
        "restricted": Zone(factory_id=factory.id, camera_id=cameras["warehouse"].id, name="Restricted Zone A", zone_type="RESTRICTED_AREA", polygon=RESTRICTED),
        "forklift": Zone(factory_id=factory.id, camera_id=cameras["warehouse"].id, name="Forklift Lane", zone_type="FORKLIFT_LANE", polygon=FORKLIFT),
    }
    db.add_all(zones.values())
    db.flush()

    rules = [
        _rule(factory, cameras["pack"], zones["packing"], "Packing hairnet", "HAIRNET_VIOLATION", "HAIRNET_MISSING", 2000, "HIGH"),
        _rule(factory, cameras["prod"], zones["production"], "Production uniform", "UNIFORM_VIOLATION", "UNIFORM_INCORRECT", 2000, "HIGH"),
        _rule(factory, cameras["machine"], zones["machine"], "Machine A danger zone", "MACHINE_DANGER_ZONE_INTRUSION", "PERSON_INSIDE", 1000, "CRITICAL"),
        _rule(factory, cameras["warehouse"], zones["restricted"], "Restricted Zone A", "RESTRICTED_AREA_INTRUSION", "PERSON_INSIDE", 1000, "HIGH"),
        _rule(factory, cameras["warehouse"], zones["forklift"], "Forklift lane", "PEDESTRIAN_IN_FORKLIFT_ZONE", "PERSON_INSIDE", 1000, "CRITICAL"),
    ]
    db.add_all(rules)
    db.flush()

    person = AIModel(name="person-detector", version="v1.0", model_type="PERSON_DETECTOR", status="ACTIVE", description="OpenCV HOG people detector (Apache-2.0). Used in REAL mode when person.onnx is not mounted. DEMO mode uses a scripted person instead.")
    ppe = AIModel(name="ppe-classifier", version="v0.1", model_type="PPE_CLASSIFIER", status="DEMO", description="Hairnet and uniform adapter. DEMO mode labels a person from the zone type. Mount ppe.onnx to classify a real crop.")
    forklift = AIModel(name="forklift-detector", version="v0.1", model_type="FORKLIFT_DETECTOR", status="DEMO", description="Optional forklift box. The forklift-lane alert is raised from a person inside the lane and does not need this model.")
    db.add_all([person, ppe, forklift])
    db.flush()
    for model in (person, ppe, forklift):
        db.add(AIModelDeployment(model_id=model.id, factory_id=factory.id, status="ACTIVE", notes="POC deployment"))

    now = datetime.now(timezone.utc)
    samples = [
        (cameras["warehouse"], zones["restricted"], rules[3], "RESTRICTED_AREA_INTRUSION", "HIGH", "NEW", 0.4, 0.91, "seed-track-1"),
        (cameras["pack"], zones["packing"], rules[0], "HAIRNET_VIOLATION", "HIGH", "CONFIRMED", 1.2, 0.88, "seed-track-2"),
        (cameras["prod"], zones["production"], rules[1], "UNIFORM_VIOLATION", "HIGH", "FALSE_POSITIVE", 2.0, 0.74, "seed-track-3"),
        (cameras["machine"], zones["machine"], rules[2], "MACHINE_DANGER_ZONE_INTRUSION", "CRITICAL", "NEW", 3.1, 0.93, "seed-track-4"),
        (cameras["warehouse"], zones["forklift"], rules[4], "PEDESTRIAN_IN_FORKLIFT_ZONE", "CRITICAL", "RESOLVED", 4.5, 0.86, "seed-track-5"),
        (cameras["pack"], zones["packing"], rules[0], "HAIRNET_VIOLATION", "MEDIUM", "CONFIRMED", 6.0, 0.81, "seed-track-6"),
        (cameras["warehouse"], zones["restricted"], rules[3], "RESTRICTED_AREA_INTRUSION", "HIGH", "NEW", 8.0, 0.9, "seed-track-7"),
        (cameras["prod"], zones["production"], rules[1], "UNIFORM_VIOLATION", "LOW", "RESOLVED", 20.0, 0.67, "seed-track-8"),
        (cameras["machine"], zones["machine"], rules[2], "MACHINE_DANGER_ZONE_INTRUSION", "CRITICAL", "FALSE_POSITIVE", 26.0, 0.58, "seed-track-9"),
    ]
    for camera, zone, rule, event_type, severity, status, hours, confidence, track in samples:
        started = now - timedelta(hours=hours)
        incident = Incident(
            factory_id=factory.id,
            camera_id=camera.id,
            zone_id=zone.id,
            rule_id=rule.id,
            event_type=event_type,
            severity=severity,
            track_id=track,
            confidence=confidence,
            started_at=started,
            ended_at=started + timedelta(seconds=18),
            status=status,
            model_name="ppe-classifier" if "VIOLATION" in event_type else "person-detector",
            model_version="v0.1" if "VIOLATION" in event_type else "v0-demo",
            ai_mode="DEMO",
            created_at=started,
            updated_at=started,
        )
        db.add(incident)
        db.flush()
        if status == "FALSE_POSITIVE":
            db.add(OperatorFeedback(incident_id=incident.id, decision=status, comment="Operator marked this sample as a false positive.", user_id=users["safety"].id, created_at=started + timedelta(minutes=5)))
        elif status in {"CONFIRMED", "RESOLVED"}:
            db.add(OperatorFeedback(incident_id=incident.id, decision=status, comment="Sample review recorded at startup.", user_id=users["safety"].id, created_at=started + timedelta(minutes=3)))
    db.commit()


def _rule(factory, camera, zone, name, event_type, condition, duration_ms, severity) -> Rule:
    return Rule(
        factory_id=factory.id,
        camera_id=camera.id,
        zone_id=zone.id,
        name=name,
        event_type=event_type,
        condition_type=condition,
        min_duration_ms=duration_ms,
        cooldown_ms=30000,
        grace_ms=1000,
        severity=severity,
        enabled=True,
        extensions={},
    )
