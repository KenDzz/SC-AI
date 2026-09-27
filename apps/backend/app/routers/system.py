import csv
import io
from collections import Counter
from datetime import datetime, timezone

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Response
from fastapi.responses import StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, Gauge, generate_latest
from sqlalchemy import text
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.models import Camera, Incident, User
from app.redis_client import get_redis
from app.services import display_status, incident_out, read_live, read_lives
from app.timeutils import FACTORY_TZ, ensure_utc, today_bounds

router = APIRouter(tags=["system"])
backend_up = Gauge("safety_backend_up", "Backend process is serving")
backend_up.set(1)


def _db_ok(db: Session) -> bool:
    try:
        db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@router.get("/health")
@router.get("/api/system/health")
def health():
    return {"status": "ok"}


@router.get("/ready")
def ready(db: Session = Depends(get_db)):
    database = "up" if _db_ok(db) else "down"
    redis_client = get_redis()
    body = {"status": "ok" if database == "up" else "degraded", "database": database, "redis": "up" if redis_client else "down"}
    return Response(content=__import__("json").dumps(body), status_code=200 if database == "up" else 503, media_type="application/json")


@router.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.get("/api/system/info")
def info(_: User = Depends(get_current_user)):
    settings = get_settings()
    client = get_redis()
    reported = None
    if client is not None:
        try:
            reported = client.get("worker:ai_mode")
        except Exception:
            reported = None
    return {
        "name": "AI Safety & Compliance Monitoring",
        "ai_mode": (reported or settings.ai_mode).upper(),
        "configured_ai_mode": settings.ai_mode.upper(),
        "worker_connected": bool(reported),
    }


@router.get("/api/system/overview")
def overview(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    start, end = today_bounds()
    today = db.query(Incident).filter(Incident.started_at >= start, Incident.started_at < end).all()
    reviewed = [item for item in today if item.status in {"CONFIRMED", "FALSE_POSITIVE", "RESOLVED"}]
    false_positives = [item for item in reviewed if item.status == "FALSE_POSITIVE"]
    rate = (len(false_positives) / len(reviewed)) if reviewed else 0.0
    buckets = Counter()
    for item in today:
        local = ensure_utc(item.started_at).astimezone(FACTORY_TZ)
        buckets[local.strftime("%H:00")] += 1
    trend = [{"hour": f"{hour:02d}:00", "count": buckets.get(f"{hour:02d}:00", 0)} for hour in range(24)]
    cameras = db.query(Camera).all()
    active = sum(1 for camera in cameras if display_status(camera, read_live(camera.id)) in {"ONLINE", "AI_PROCESSING"})
    latest_rows = (
        db.query(Incident)
        .options(joinedload(Incident.camera), joinedload(Incident.zone), joinedload(Incident.rule))
        .order_by(Incident.started_at.desc())
        .limit(8)
        .all()
    )
    return {
        "active_cameras": active,
        "camera_count": len(cameras),
        "incidents_today": len(today),
        "critical_incidents": sum(1 for item in today if item.severity == "CRITICAL"),
        "confirmed_incidents": sum(1 for item in today if item.status == "CONFIRMED"),
        "false_positive_rate": round(rate, 4),
        "false_positive_count": len(false_positives),
        "reviewed_count": len(reviewed),
        "trend": trend,
        "latest": [incident_out(row).model_dump(mode="json") for row in latest_rows],
    }


@router.get("/api/system/evaluation")
def evaluation(format: str = "json", db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    incidents = db.query(Incident).all()
    reviewed = [item for item in incidents if item.status in {"CONFIRMED", "FALSE_POSITIVE", "RESOLVED"}]
    false_positives = [item for item in reviewed if item.status == "FALSE_POSITIVE"]
    confidences = [item.confidence for item in incidents if item.confidence is not None]
    by_type = Counter(item.event_type for item in incidents)
    lives = read_lives()
    payload = {
        "incidents": len(incidents),
        "reviewed": len(reviewed),
        "false_positives": len(false_positives),
        "false_positive_rate": round((len(false_positives) / len(reviewed)) if reviewed else 0.0, 4),
        "average_confidence": round(sum(confidences) / len(confidences), 4) if confidences else None,
        "by_event_type": dict(by_type),
        "frames_processed": sum(int(item.get("frames_processed") or 0) for item in lives),
        "dropped_frames": sum(int(item.get("dropped_frames") or 0) for item in lives),
        "average_inference_ms": round(
            sum(float(item.get("inference_ms") or 0) for item in lives) / len(lives),
            2,
        ) if lives else None,
        "cameras_reporting": len(lives),
        "notes": [
            "False positive rate is false positives divided by incidents an operator has reviewed.",
            "These figures describe alert volume and review. They are not a model accuracy score.",
            "Recall needs missed-event labels, which this POC does not collect.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    if format == "csv":
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["metric", "value"])
        for key, value in payload.items():
            if key == "notes":
                continue
            writer.writerow([key, value])
        return Response(content=buffer.getvalue(), media_type="text/csv")
    return payload


@router.get("/api/events/stream")
async def stream(_: User = Depends(get_current_user)):
    settings = get_settings()

    async def events():
        client = aioredis.from_url(settings.redis_url)
        pubsub = client.pubsub()
        try:
            await pubsub.subscribe("incidents")
            yield "event: ready\ndata: {}\n\n"
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=15.0)
                if message and message.get("type") == "message":
                    data = message["data"]
                    if isinstance(data, bytes):
                        data = data.decode()
                    yield f"data: {data}\n\n"
                else:
                    yield ": keepalive\n\n"
        finally:
            await pubsub.close()
            await client.close()

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
