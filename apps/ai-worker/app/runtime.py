"""Per-camera loop: sample a frame, detect, track, apply zone rules, publish incidents."""

import base64
import logging
import threading
import time
from collections import Counter, deque
from datetime import datetime, timezone

from app.api_client import ApiClient
from app.config import Settings
from app.detectors import HogPersonDetector, UnknownPPEClassifier, build_detectors
from app.drawing import annotate, jpeg_bytes
from app.logging_utils import event
from app.metrics import camera_fps, camera_up, detections_total, dropped_frames, frames_processed, incidents_created, inference_latency
from app.rule_engine import Observation, RuleConfig, RuleEngine
from app.sources import FrameSource
from app.storage import ObjectStore
from app.tracker import PersonTracker
from app.zone_engine import bbox_center_in_polygon

log = logging.getLogger("worker.runtime")
PPE_EVENTS = {"HAIRNET_VIOLATION", "UNIFORM_VIOLATION"}


def iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def iou(a: list[float], b: list[float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1) + max(0.0, bx2 - bx1) * max(0.0, by2 - by1) - inter
    if area <= 0:
        return 0.0
    return inter / area


def normalize(box: list[float], width: int, height: int) -> tuple[float, float, float, float]:
    return (box[0] / width, box[1] / height, box[2] / width, box[3] / height)


def rule_config(rule: dict) -> RuleConfig:
    return RuleConfig(
        id=rule["id"],
        zone_id=rule["zone_id"],
        condition_type=rule["condition_type"],
        event_type=rule["event_type"],
        severity=rule["severity"],
        min_duration_s=float(rule["min_duration_ms"]) / 1000.0,
        cooldown_s=float(rule["cooldown_ms"]) / 1000.0,
        grace_s=float(rule["grace_ms"]) / 1000.0,
    )


def crop_of(frame, box: list[float]):
    height, width = frame.shape[:2]
    x1 = max(0, min(width - 1, int(box[0])))
    y1 = max(0, min(height - 1, int(box[1])))
    x2 = max(x1 + 1, min(width, int(box[2])))
    y2 = max(y1 + 1, min(height, int(box[3])))
    return frame[y1:y2, x1:x2]


class CameraLoop:
    def __init__(self, camera_id: str, settings: Settings, stop: threading.Event):
        self.camera_id = camera_id
        self.settings = settings
        self.stop = stop
        self.api = ApiClient(settings)
        self.store = ObjectStore(settings)
        self.source = FrameSource(camera_id)
        self.engine = RuleEngine()
        self.tracker = None
        self.tracker_fps = None
        self.hold_until = 0.0
        self.frame_times = deque(maxlen=20)
        self.frames = 0
        self.dropped = 0
        self.last_preview = 0.0
        self.last_raw_preview = 0.0
        self.ppe_votes: dict[str, deque] = {}
        self.detector, self.ppe, self.person_name, self.person_version, self.ppe_name, self.ppe_version = self._load_models()

    def _load_models(self):
        try:
            return build_detectors(self.settings.ai_mode, self.settings.model_path, self.settings.ai_device)
        except Exception:
            log.exception("model adapter failed; person detection uses HOG and PPE stays UNKNOWN")
            return HogPersonDetector(), UnknownPPEClassifier(), "person-detector", "hog-v1", "ppe-classifier", "unloaded"

    def close(self) -> None:
        self.source.close()
        self.api.http.close()
        camera_up.labels(camera_id=self.camera_id).set(0)

    def run(self) -> None:
        log.info("camera loop started", extra={"camera_id": self.camera_id})
        while not self.stop.is_set():
            camera = self._camera()
            if camera is None:
                camera_up.labels(camera_id=self.camera_id).set(0)
                self.stop.wait(2)
                continue
            if not camera.get("enabled"):
                self._heartbeat(camera, "DISABLED", [], 0, 0)
                self.stop.wait(2)
                continue
            started = time.perf_counter()
            try:
                self._step(camera)
            except Exception:
                log.exception("camera step failed", extra={"camera_id": self.camera_id})
                self.stop.wait(2)
                continue
            fps = max(1, int(camera.get("ai_fps") or self.settings.default_ai_fps))
            elapsed = time.perf_counter() - started
            interval = 1.0 / fps
            if elapsed > interval:
                self.dropped += 1
                dropped_frames.labels(camera_id=self.camera_id).inc()
            else:
                self.stop.wait(interval - elapsed)

    def _camera(self) -> dict | None:
        try:
            cameras = self.api.list_cameras()
        except Exception:
            log.warning("camera config request failed", extra={"camera_id": self.camera_id})
            return None
        for camera in cameras:
            if camera["id"] == self.camera_id:
                assigned = camera.get("assigned_worker")
                if assigned and assigned != self.settings.worker_id:
                    return None
                return camera
        return None

    def _step(self, camera: dict) -> None:
        if camera.get("simulate_pending"):
            longest = max((float(rule["min_duration_ms"]) for rule in camera.get("rules") or []), default=1000.0)
            self.hold_until = time.time() + longest / 1000.0 + 1.5
            try:
                self.api.ack_simulate(camera["id"])
            except Exception:
                log.warning("simulate ack failed", extra={"camera_id": camera["id"]})
        frame, source_state = self.source.read(camera, self.store, self.settings)
        if frame is None:
            camera_up.labels(camera_id=camera["id"]).set(0)
            self._heartbeat(camera, "OFFLINE", [], 0, 0)
            return
        fps_setting = max(1, int(camera.get("ai_fps") or self.settings.default_ai_fps))
        if self.tracker is None or self.tracker_fps != fps_setting:
            self.tracker = PersonTracker(frame_rate=fps_setting)
            self.tracker_fps = fps_setting
        now = time.time()
        hold = now < self.hold_until
        infer_started = time.perf_counter()
        detections = self.detector.detect(frame, camera.get("zones") or [], now, hold)
        tracks = self.tracker.update(detections)
        enriched = self._enrich(frame, camera, detections, tracks)
        latency = time.perf_counter() - infer_started
        inference_latency.labels(camera_id=camera["id"]).observe(latency)
        frames_processed.labels(camera_id=camera["id"]).inc()
        detections_total.labels(camera_id=camera["id"]).inc(len(detections))
        self.frames += 1
        self.frame_times.append(now)
        self._apply_rules(camera, frame, enriched, now)
        annotated = annotate(frame, camera.get("zones") or [], enriched)
        camera_up.labels(camera_id=camera["id"]).set(1)
        achieved = self._achieved_fps()
        camera_fps.labels(camera_id=camera["id"]).set(achieved)
        self._maybe_store_preview(camera["id"], frame, annotated, fps_setting)
        self._heartbeat(camera, "AI_PROCESSING", enriched, latency * 1000.0, achieved, source_state)

    def _enrich(self, frame, camera: dict, detections: list[dict], tracks: list[dict]) -> list[dict]:
        height, width = frame.shape[:2]
        zones = camera.get("zones") or []
        enriched = []
        for track in tracks:
            hint = _match_hint(track["bbox_xyxy"], detections)
            box = normalize(track["bbox_xyxy"], width, height)
            zone_types = [
                zone["zone_type"]
                for zone in zones
                if bbox_center_in_polygon(zone.get("polygon"), box)
            ]
            hairnet, uniform, ppe_confidence = "UNKNOWN", "UNKNOWN", 0.0
            if track["class_name"] == "person":
                ppe = self.ppe.classify(
                    crop_of(frame, track["bbox_xyxy"]),
                    {"ppe_mode": (hint or {}).get("ppe_mode", "zone"), "zone_types": zone_types},
                )
                hairnet, uniform, ppe_confidence = self._stable_ppe(
                    track["track_id"],
                    ppe["hairnet"],
                    ppe["uniform"],
                    float(ppe.get("confidence") or 0.0),
                )
            enriched.append({**track, "bbox_norm": box, "hairnet": hairnet, "uniform": uniform, "ppe_confidence": ppe_confidence, "zone_types": zone_types})
        stale = set(self.ppe_votes) - {track["track_id"] for track in tracks}
        for track_id in stale:
            self.ppe_votes.pop(track_id, None)
        return enriched

    def _stable_ppe(self, track_id: str, hairnet: str, uniform: str, confidence: float) -> tuple[str, str, float]:
        history = self.ppe_votes.setdefault(track_id, deque(maxlen=6))
        history.append((hairnet, uniform, confidence))

        def settle(index: int, allowed: set[str]) -> tuple[str, float]:
            chosen = [item for item in history if item[index] in allowed]
            if len(history) < 3 or not chosen:
                return "UNKNOWN", 0.0
            label, count = Counter(item[index] for item in chosen).most_common(1)[0]
            if count < 3:
                return "UNKNOWN", 0.0
            scores = [item[2] for item in chosen if item[index] == label]
            return label, sum(scores) / len(scores)

        stable_hairnet, hairnet_score = settle(0, {"YES", "NO"})
        stable_uniform, uniform_score = settle(1, {"CORRECT", "INCORRECT"})
        return stable_hairnet, stable_uniform, round(max(hairnet_score, uniform_score), 3)

    def _apply_rules(self, camera: dict, frame, tracks: list[dict], now: float) -> None:
        rules = [rule for rule in camera.get("rules") or [] if rule.get("enabled")]
        configs = {rule["id"]: rule_config(rule) for rule in rules}
        zones = {zone["id"]: zone for zone in camera.get("zones") or []}
        visible: set[str] = set()
        actions = []
        for track in tracks:
            if track["class_name"] != "person":
                continue
            visible.add(track["track_id"])
            for rule in rules:
                zone = zones.get(rule["zone_id"])
                if zone is None:
                    continue
                inside = bbox_center_in_polygon(zone.get("polygon"), track["bbox_norm"])
                confidence = track["ppe_confidence"] if rule["condition_type"] != "PERSON_INSIDE" else track["confidence"]
                actions.extend(
                    self.engine.update(
                        configs[rule["id"]],
                        Observation(
                            track_id=track["track_id"],
                            timestamp=now,
                            inside=inside,
                            hairnet=track["hairnet"],
                            uniform=track["uniform"],
                            confidence=float(confidence or 0.0),
                            bbox=track["bbox_norm"],
                            class_name="person",
                        ),
                    )
                )
        actions.extend(self.engine.expire_missing(configs, now, visible))
        annotated = None
        for action in actions:
            if action.kind == "open":
                self._open(camera, frame, action, annotated_frame=(annotated if annotated is not None else annotate(frame, camera.get("zones") or [], tracks)))
            elif action.kind == "close" and action.incident_id:
                try:
                    self.api.close_incident(action.incident_id, iso(action.ended_at or now))
                    event(log, "incident closed", camera_id=camera["id"], track_id=action.track_id, rule_id=action.rule_id, incident_id=action.incident_id)
                except Exception:
                    log.exception("incident close failed", extra={"camera_id": camera["id"], "incident_id": action.incident_id, "rule_id": action.rule_id, "track_id": action.track_id})

    def _open(self, camera: dict, frame, action, annotated_frame) -> None:
        use_ppe = action.event_type in PPE_EVENTS
        snapshot = jpeg_bytes(annotated_frame)
        crop = crop_of(frame, [action.bbox[0] * frame.shape[1], action.bbox[1] * frame.shape[0], action.bbox[2] * frame.shape[1], action.bbox[3] * frame.shape[0]])
        payload = {
            "factory_id": camera["factory_id"],
            "camera_id": camera["id"],
            "zone_id": action.zone_id,
            "rule_id": action.rule_id,
            "event_type": action.event_type,
            "severity": action.severity,
            "track_id": action.track_id,
            "confidence": round(float(action.confidence), 4),
            "started_at": iso(action.started_at),
            "model_name": self.ppe_name if use_ppe else self.person_name,
            "model_version": self.ppe_version if use_ppe else self.person_version,
            "ai_mode": self.settings.ai_mode.upper(),
            "snapshot_base64": base64.b64encode(snapshot).decode("ascii"),
            "crop_base64": base64.b64encode(jpeg_bytes(crop, 80)).decode("ascii") if crop is not None and crop.size else None,
        }
        try:
            body = self.api.open_incident(payload)
        except Exception:
            log.exception("incident create failed", extra={"camera_id": camera["id"], "rule_id": action.rule_id, "track_id": action.track_id})
            return
        reason = body.get("reason")
        if reason == "cooldown":
            self.engine.force_cooldown(action.rule_id, action.track_id, time.time() + 1.0)
            return
        self.engine.attach_incident(action.rule_id, action.track_id, body["id"])
        if reason == "created":
            incidents_created.labels(camera_id=camera["id"]).inc()
            event(
                log,
                "incident opened",
                camera_id=camera["id"],
                track_id=action.track_id,
                rule_id=action.rule_id,
                incident_id=body["id"],
            )

    def _maybe_store_preview(self, camera_id: str, raw, annotated, fps: int) -> None:
        now = time.time()
        preview_every = 1.0 / min(max(fps, 1), 10)
        try:
            if now - self.last_preview >= preview_every:
                self.last_preview = now
                self.store.put_bytes(f"cameras/{camera_id}/latest.jpg", jpeg_bytes(annotated), "image/jpeg")
            if now - self.last_raw_preview >= 1.0:
                self.last_raw_preview = now
                self.store.put_bytes(f"cameras/{camera_id}/latest_raw.jpg", jpeg_bytes(raw), "image/jpeg")
        except Exception:
            log.warning("preview upload failed", extra={"camera_id": camera_id})

    def _heartbeat(self, camera: dict, status: str, tracks: list[dict], inference_ms: float, achieved: float, source_state: str = "") -> None:
        payload = {
            "status": status,
            "frames_processed": self.frames,
            "dropped_frames": self.dropped,
            "inference_ms": round(inference_ms, 2),
            "detections": len(tracks),
            "ai_fps": round(achieved, 2),
            "ai_mode": self.settings.ai_mode.upper(),
            "source_state": source_state,
            "tracks": [
                {
                    "track_id": track["track_id"],
                    "bbox": list(track["bbox_norm"]),
                    "class_name": track["class_name"],
                    "confidence": round(float(track["confidence"]), 3),
                    "hairnet": track.get("hairnet"),
                    "uniform": track.get("uniform"),
                }
                for track in tracks
            ],
        }
        try:
            self.api.heartbeat(camera["id"], payload)
        except Exception:
            log.warning("heartbeat failed", extra={"camera_id": camera["id"]})

    def _achieved_fps(self) -> float:
        if len(self.frame_times) < 2:
            return 0.0
        span = self.frame_times[-1] - self.frame_times[0]
        if span <= 0:
            return 0.0
        return (len(self.frame_times) - 1) / span


def _match_hint(box: list[float], detections: list[dict]) -> dict | None:
    best = None
    best_score = 0.3
    for detection in detections:
        score = iou(box, detection["bbox_xyxy"])
        if score > best_score:
            best = detection
            best_score = score
    return best
