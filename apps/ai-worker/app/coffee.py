"""Coffee-belt quality and counting.

A bean is counted once, when its centre crosses the belt's mid line going down
the frame. Green and roasted belts grade that bean. The count belt only totals
quantity. Defect rate uses the most recent window of counted beans.
"""

from collections import deque
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from app.zone_engine import point_in_polygon

GREEN_ZONE = "GREEN_COFFEE_LINE"
ROASTED_ZONE = "ROASTED_COFFEE_LINE"
COUNT_ZONE = "COFFEE_COUNT_LINE"
COFFEE_ZONES = {GREEN_ZONE, ROASTED_ZONE, COUNT_ZONE}

STAGE_OF = {GREEN_ZONE: "green", ROASTED_ZONE: "roasted", COUNT_ZONE: "count"}
EVENT_FOR_STAGE = {"green": "GREEN_COFFEE_DEFECT_RATE", "roasted": "ROASTED_COFFEE_DEFECT_RATE"}
COFFEE_EVENTS = set(EVENT_FOR_STAGE.values())

# coffee.onnx class ids. Good is shared. The belt stage drops classes that do not belong to it.
ONNX_CLASS_NAMES = {
    0: "good",
    1: "black",
    2: "broken",
    3: "fade",
    4: "sour",
    5: "quaker",
    6: "burnt",
    7: "insect",
    8: "mould",
}
GREEN_IDS = {0, 1, 2, 3, 4}
ROASTED_IDS = {0, 5, 6, 7, 8}

ALLOWED = {
    "green": {"good", "black", "broken", "fade", "sour"},
    "roasted": {"good", "quaker", "burnt", "insect", "mould"},
    "count": {"bean"},
}
DEFECTS = {
    "green": {"black", "broken", "fade", "sour"},
    "roasted": {"quaker", "burnt", "insect", "mould"},
    "count": set(),
}
CYCLES = {
    "green": ("black", "broken", "fade", "sour", "good"),
    "roasted": ("quaker", "burnt", "insect", "mould", "good"),
    "count": ("bean", "bean", "bean", "bean", "bean"),
}
SPEED = 0.45
SLOTS = 5


def stage_of(zone_type: str | None) -> str | None:
    return STAGE_OF.get(zone_type or "")


def count_line_y(polygon: list) -> float:
    ys = [float(point[1]) for point in polygon]
    return (min(ys) + max(ys)) / 2.0


def class_for_stage(stage: str, class_id: int) -> str | None:
    class_id = int(class_id)
    name = ONNX_CLASS_NAMES.get(class_id)
    if name is None:
        return None
    if stage == "count":
        return "bean"
    if stage == "green" and class_id in GREEN_IDS:
        return name
    if stage == "roasted" and class_id in ROASTED_IDS:
        return name
    return None


YOLO_CHANNELS = 4 + len(ONNX_CLASS_NAMES)


def detections_from_rows(rows, stage: str, frame_w: int, frame_h: int, input_w: int, input_h: int) -> list[dict]:
    output = np.asarray(rows)
    if output.ndim == 3:
        output = output[0]
    if output.ndim != 2 or output.shape[1] < 6:
        return []
    sx = frame_w / max(input_w, 1)
    sy = frame_h / max(input_h, 1)
    found = []
    for row in output:
        score = float(row[4])
        if score < 0.35:
            continue
        name = class_for_stage(stage, int(row[5]))
        if name is None:
            continue
        x1, y1, x2, y2 = float(row[0]) * sx, float(row[1]) * sy, float(row[2]) * sx, float(row[3]) * sy
        found.append(
            {
                "class_name": name,
                "confidence": score,
                "bbox_xyxy": [x1, y1, x2, y2],
                "cx": ((x1 + x2) / 2.0) / max(frame_w, 1),
                "cy": ((y1 + y2) / 2.0) / max(frame_h, 1),
            }
        )
    return found


class CoffeeLine:
    def __init__(self, stage: str):
        self.stage = stage
        self.line_y = 0.5
        self.samples: deque[str] = deque(maxlen=400)
        self.total = 0
        self._seen: set[str] = set()
        self._prev: dict[str, float] = {}

    def set_line(self, y: float) -> None:
        self.line_y = float(y)

    def observe(self, beans: list[dict]) -> None:
        for bean in beans:
            track_id = str(bean["track_id"])
            label = self._label(bean.get("class_name") or "")
            cy = float(bean["cy"])
            previous = self._prev.get(track_id)
            self._prev[track_id] = cy
            if label is None or previous is None or track_id in self._seen:
                continue
            if previous < self.line_y <= cy:
                self._seen.add(track_id)
                self.samples.append(label)
                self.total += 1

    def summary(self, window: int) -> dict:
        recent = list(self.samples)[-max(int(window), 1) :]
        counts: dict[str, int] = {}
        for label in recent:
            counts[label] = counts.get(label, 0) + 1
        defects = sum(count for label, count in counts.items() if label in DEFECTS[self.stage])
        return {
            "total": self.total,
            "window_total": len(recent),
            "defects": defects,
            "defect_rate": (defects / len(recent)) if recent else 0.0,
            "by_class": counts,
        }

    def _label(self, name: str) -> str | None:
        if self.stage == "count":
            return "bean"
        if name in ALLOWED[self.stage]:
            return name
        return None


class BeanTracker:
    def __init__(self, max_step: float = 0.15):
        self.max_step = max_step
        self.next_id = 1
        self.active: list[dict] = []

    def update(self, beans: list[dict]) -> list[dict]:
        unused = set(range(len(self.active)))
        assigned = []
        for bean in beans:
            best = None
            best_distance = self.max_step
            for index in unused:
                item = self.active[index]
                distance = ((item["cx"] - bean["cx"]) ** 2 + (item["cy"] - bean["cy"]) ** 2) ** 0.5
                if distance < best_distance:
                    best, best_distance = index, distance
            if best is None:
                track_id = str(self.next_id)
                self.next_id += 1
                self.active.append({"id": track_id, "cx": bean["cx"], "cy": bean["cy"], "missed": 0})
            else:
                unused.remove(best)
                track_id = self.active[best]["id"]
                self.active[best]["cx"] = bean["cx"]
                self.active[best]["cy"] = bean["cy"]
                self.active[best]["missed"] = 0
            assigned.append({**bean, "track_id": track_id})
        for index in sorted(unused, reverse=True):
            self.active[index]["missed"] += 1
            if self.active[index]["missed"] > 8:
                self.active.pop(index)
        return assigned


@dataclass
class AlarmSignal:
    kind: str
    incident_id: str | None = None
    started_at: float = 0.0
    ended_at: float | None = None


class DefectAlarm:
    def __init__(self):
        self.phase = "idle"
        self.started_at = 0.0
        self.last_high_at = 0.0
        self.cooldown_until = 0.0
        self.incident_id: str | None = None

    def attach(self, incident_id: str) -> None:
        self.incident_id = incident_id
        self.phase = "open"

    def force_cooldown(self, until: float) -> None:
        self.phase = "cooldown"
        self.cooldown_until = until
        self.incident_id = None

    def update(self, high: bool, now: float, min_duration_s: float, cooldown_s: float, grace_s: float) -> AlarmSignal | None:
        if self.phase == "cooldown" and now < self.cooldown_until:
            return None
        if high:
            if self.phase in {"idle", "cooldown"}:
                self.phase = "pending"
                self.started_at = now
                self.last_high_at = now
                self.incident_id = None
                return None
            self.last_high_at = now
            if self.phase == "pending" and now - self.started_at >= min_duration_s:
                self.phase = "open"
                return AlarmSignal(kind="open", started_at=self.started_at)
            return None
        if self.phase not in {"pending", "open"}:
            return None
        if now - self.last_high_at <= grace_s:
            return None
        if self.phase == "open" and self.incident_id:
            signal = AlarmSignal(kind="close", incident_id=self.incident_id, started_at=self.started_at, ended_at=self.last_high_at)
            self.phase = "cooldown"
            self.cooldown_until = now + cooldown_s
            self.incident_id = None
            return signal
        if self.phase == "open":
            self.phase = "cooldown"
            self.cooldown_until = now + cooldown_s
            return None
        self.phase = "idle"
        return None


@dataclass
class CoffeeAction:
    kind: str
    rule_id: str
    zone_id: str
    track_id: str
    event_type: str
    severity: str
    confidence: float
    started_at: float
    ended_at: float | None
    bbox: tuple[float, float, float, float]
    incident_id: str | None = None


class CoffeeMonitor:
    """Tracks beans per belt and opens a defect-rate incident for green and roasted lines."""

    def __init__(self):
        self.trackers: dict[str, BeanTracker] = {}
        self.lines: dict[str, CoffeeLine] = {}
        self.alarms: dict[str, DefectAlarm] = {}

    def step(self, beans: list[dict], zones: list[dict], rules: list[dict], now: float) -> tuple[list[dict], list[dict], list[CoffeeAction]]:
        rules_by_zone: dict[str, list[dict]] = {}
        for rule in rules:
            if rule.get("enabled", True) and rule.get("condition_type") == "DEFECT_RATE":
                rules_by_zone.setdefault(rule["zone_id"], []).append(rule)
        overlays: list[dict] = []
        reports: list[dict] = []
        actions: list[CoffeeAction] = []
        for zone in zones:
            stage = stage_of(zone.get("zone_type"))
            polygon = zone.get("polygon") or []
            if stage is None or len(polygon) < 3:
                continue
            inside = [bean for bean in beans if point_in_polygon(polygon, float(bean["cx"]), float(bean["cy"]))]
            tracked = self.trackers.setdefault(zone["id"], BeanTracker()).update(inside)
            line = self.lines.setdefault(zone["id"], CoffeeLine(stage))
            line.set_line(count_line_y(polygon))
            line.observe(tracked)
            zone_rules = rules_by_zone.get(zone["id"], [])
            window = 12
            for rule in zone_rules:
                window = int((rule.get("extensions") or {}).get("window") or window)
            summary = line.summary(window=window)
            reports.append(
                {
                    "zone_id": zone["id"],
                    "name": zone.get("name") or zone.get("zone_type"),
                    "stage": stage,
                    "in_frame": len(tracked),
                    **summary,
                }
            )
            overlays.extend(tracked)
            if stage == "count":
                continue
            bounds = _bounds(polygon)
            for rule in zone_rules:
                if rule.get("event_type") != EVENT_FOR_STAGE[stage]:
                    continue
                extensions = rule.get("extensions") or {}
                limit = float(extensions.get("max_defect_rate", 0.15))
                rule_window = int(extensions.get("window") or 12)
                view = line.summary(window=rule_window)
                high = view["window_total"] >= rule_window and view["defect_rate"] >= limit
                alarm = self.alarms.setdefault(rule["id"], DefectAlarm())
                signal = alarm.update(
                    high,
                    now,
                    min_duration_s=float(rule.get("min_duration_ms") or 0) / 1000.0,
                    cooldown_s=float(rule.get("cooldown_ms") or 0) / 1000.0,
                    grace_s=float(rule.get("grace_ms") or 0) / 1000.0,
                )
                if signal is None:
                    continue
                actions.append(
                    CoffeeAction(
                        kind=signal.kind,
                        rule_id=rule["id"],
                        zone_id=zone["id"],
                        track_id=f"line-{zone['id']}",
                        event_type=rule["event_type"],
                        severity=rule.get("severity") or "HIGH",
                        confidence=float(view["defect_rate"]),
                        started_at=signal.started_at,
                        ended_at=signal.ended_at,
                        bbox=bounds,
                        incident_id=signal.incident_id,
                    )
                )
        return overlays, reports, actions

    def attach(self, rule_id: str, incident_id: str) -> None:
        alarm = self.alarms.get(rule_id)
        if alarm is not None:
            alarm.attach(incident_id)

    def force_cooldown(self, rule_id: str, until: float) -> None:
        alarm = self.alarms.get(rule_id)
        if alarm is None:
            alarm = DefectAlarm()
            self.alarms[rule_id] = alarm
        alarm.force_cooldown(until)


def _bounds(polygon: list) -> tuple[float, float, float, float]:
    xs = [float(point[0]) for point in polygon]
    ys = [float(point[1]) for point in polygon]
    return (min(xs), min(ys), max(xs), max(ys))


def scripted_beans(zone: dict, now: float, hold: bool) -> list[dict]:
    stage = stage_of(zone.get("zone_type"))
    polygon = zone.get("polygon") or []
    if stage is None or len(polygon) < 3:
        return []
    xs = [float(point[0]) for point in polygon]
    ys = [float(point[1]) for point in polygon]
    x0, x1 = min(xs) + 0.04, max(xs) - 0.04
    y0, y1 = min(ys) + 0.03, max(ys) - 0.03
    if x1 <= x0 or y1 <= y0:
        return []
    beans = []
    cycle = CYCLES[stage]
    for index in range(SLOTS):
        progress = 0.72 if hold else (now * SPEED + index / SLOTS) % 1.0
        beans.append(
            {
                "class_name": cycle[index],
                "confidence": 0.9,
                "cx": x0 + (x1 - x0) * ((index + 0.5) / SLOTS),
                "cy": y0 + (y1 - y0) * progress,
            }
        )
    return beans


def _centered_box(cx: float, cy: float, width: int, height: int) -> list[float]:
    bw, bh = 0.04, 0.055
    return [
        max(0.0, cx - bw / 2) * width,
        max(0.0, cy - bh / 2) * height,
        min(1.0, cx + bw / 2) * width,
        min(1.0, cy + bh / 2) * height,
    ]


class DemoCoffeeDetector:
    name = "coffee-line"
    version = "v0-demo"

    def detect(self, frame, zones: list[dict], now: float, hold: bool) -> list[dict]:
        height, width = frame.shape[:2]
        found = []
        for zone in zones:
            for bean in scripted_beans(zone, now, hold):
                found.append({**bean, "bbox_xyxy": _centered_box(bean["cx"], bean["cy"], width, height)})
        return found


class BlobCoffeeDetector:
    """Colour and shape fallback used when coffee.onnx is not installed."""

    name = "coffee-line"
    version = "color-v2"

    def detect(self, frame, zones: list[dict], now: float, hold: bool) -> list[dict]:
        del now, hold
        found = []
        for zone in zones:
            stage = stage_of(zone.get("zone_type"))
            polygon = zone.get("polygon") or []
            if stage is None or len(polygon) < 3:
                continue
            found.extend(self.detect_in_polygon(frame, polygon, stage))
        return found

    def detect_in_polygon(self, frame, polygon: list, stage: str) -> list[dict]:
        height, width = frame.shape[:2]
        if height < 8 or width < 8 or stage not in ALLOWED:
            return []
        region = np.zeros((height, width), dtype=np.uint8)
        contour = np.array([[int(float(x) * width), int(float(y) * height)] for x, y in polygon], dtype=np.int32)
        if len(contour) < 3:
            return []
        cv2.fillPoly(region, [contour], 255)
        mask = _beans_against_belt(frame, region)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        found = []
        for item in _bean_contours(mask, contours):
            x, y, w, h = cv2.boundingRect(item)
            perimeter = float(cv2.arcLength(item, True))
            area = float(cv2.contourArea(item))
            circularity = (4.0 * np.pi * area / (perimeter * perimeter)) if perimeter else 0.0
            crop = frame[y : y + h, x : x + w]
            name = grade_crop(crop, stage, float(circularity))
            if name is None:
                continue
            found.append(
                {
                    "class_name": name,
                    "confidence": 0.8,
                    "bbox_xyxy": [float(x), float(y), float(x + w), float(y + h)],
                    "cx": (x + w / 2.0) / width,
                    "cy": (y + h / 2.0) / height,
                }
            )
        return found


def detections_from_yolo_output(
    output,
    stage: str,
    frame_w: int,
    frame_h: int,
    input_w: int,
    input_h: int,
    pad_x: float = 0,
    pad_y: float = 0,
    gain: float = 1,
) -> list[dict]:
    """Ultralytics YOLO head: (1, 4+classes, anchors) or (1, anchors, 4+classes).

    Columns are cx, cy, w, h, then one score per class id. Coordinates are in
    the letterboxed model image. NMS keeps one box when beans overlap.
    """
    rows = np.squeeze(np.asarray(output, dtype=np.float32))
    if rows.ndim != 2:
        return []
    if rows.shape[0] == YOLO_CHANNELS:
        rows = rows.T
    elif rows.shape[1] != YOLO_CHANNELS:
        return []
    boxes: list[list[float]] = []
    scores: list[float] = []
    names: list[str] = []
    gain = gain if gain else 1.0
    for row in rows:
        cx, cy, width, height = (float(value) for value in row[:4])
        if max(abs(cx), abs(cy), abs(width), abs(height)) <= 1.5:
            cx *= input_w
            cy *= input_h
            width *= input_w
            height *= input_h
        class_id = int(np.argmax(row[4:]))
        score = float(row[4 + class_id])
        if score < 0.35:
            continue
        name = class_for_stage(stage, class_id)
        if name is None:
            continue
        x1 = (cx - width / 2.0 - pad_x) / gain
        y1 = (cy - height / 2.0 - pad_y) / gain
        x2 = (cx + width / 2.0 - pad_x) / gain
        y2 = (cy + height / 2.0 - pad_y) / gain
        boxes.append([x1, y1, max(x2 - x1, 0.0), max(y2 - y1, 0.0)])
        scores.append(score)
        names.append(name)
    if not boxes:
        return []
    chosen = cv2.dnn.NMSBoxes(boxes, scores, 0.0, 0.45)
    if chosen is None or len(chosen) == 0:
        return []
    found = []
    for index in np.asarray(chosen).reshape(-1):
        index = int(index)
        x, y, width, height = boxes[index]
        x1, y1, x2, y2 = x, y, x + width, y + height
        found.append(
            {
                "class_name": names[index],
                "confidence": scores[index],
                "bbox_xyxy": [x1, y1, x2, y2],
                "cx": ((x1 + x2) / 2.0) / max(frame_w, 1),
                "cy": ((y1 + y2) / 2.0) / max(frame_h, 1),
            }
        )
    return found


def beans_from_onnx_output(
    output,
    stage: str,
    frame_w: int,
    frame_h: int,
    input_w: int,
    input_h: int,
    pad_x: float = 0,
    pad_y: float = 0,
    gain: float = 1,
) -> list[dict]:
    rows = np.squeeze(np.asarray(output))
    if rows.ndim == 2 and (rows.shape[0] == YOLO_CHANNELS or rows.shape[1] == YOLO_CHANNELS):
        return detections_from_yolo_output(output, stage, frame_w, frame_h, input_w, input_h, pad_x, pad_y, gain)
    return detections_from_rows(output, stage, frame_w, frame_h, input_w, input_h)


def _beans_against_belt(frame: np.ndarray, region: np.ndarray) -> np.ndarray:
    """Beans are the pixels clearly lighter or darker than the belt inside the zone.

    A grey lab belt and a dark factory belt both work. The belt colour is the
    30th percentile of brightness, so a pile of beans does not become the background.
    """
    value = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)[:, :, 2].astype(np.int16)
    inside = region > 0
    if int(inside.sum()) < 30:
        return np.zeros(region.shape, dtype=np.uint8)
    belt = float(np.percentile(value[inside], 30))
    beans = inside & ((value > belt + 18) | (value < belt - 18))
    mask = beans.astype(np.uint8) * 255
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)


def _bean_contours(mask: np.ndarray, contours: list):
    """Yield one contour per bean. A touching pile is split; a rail-sized blob is dropped."""
    for item in contours:
        area = float(cv2.contourArea(item))
        if area < 80:
            continue
        if area < 3500:
            yield item
            continue
        parts = _split_pile(mask, item)
        if len(parts) < 2:
            continue
        for part in parts:
            part_area = float(cv2.contourArea(part))
            if 80 <= part_area < 3500:
                yield part


def _split_pile(mask: np.ndarray, contour: np.ndarray) -> list:
    x, y, width, height = cv2.boundingRect(contour)
    if width < 3 or height < 3:
        return []
    local = np.zeros((height, width), dtype=np.uint8)
    shifted = contour.copy()
    shifted[:, 0, 0] -= x
    shifted[:, 0, 1] -= y
    cv2.drawContours(local, [shifted], -1, 255, -1)
    distance = cv2.distanceTransform(local, cv2.DIST_L2, 5)
    if float(distance.max()) < 3:
        return []
    _, peaks = cv2.threshold(distance, max(2.5, 0.35 * float(distance.max())), 255, cv2.THRESH_BINARY)
    count, markers = cv2.connectedComponents(peaks.astype(np.uint8))
    if count < 2:
        return []
    markers = markers + 1
    markers[local == 0] = 0
    markers = cv2.watershed(cv2.cvtColor(local, cv2.COLOR_GRAY2BGR), markers.astype(np.int32))
    parts = []
    for label in range(2, int(markers.max()) + 1):
        piece = ((markers == label).astype(np.uint8)) * 255
        found, _ = cv2.findContours(piece, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for part in found:
            part = part.copy()
            part[:, 0, 0] += x
            part[:, 0, 1] += y
            parts.append(part)
    return parts


def grade_crop(crop: np.ndarray, stage: str, circularity: float) -> str | None:
    if crop is None or crop.size == 0 or stage not in ALLOWED:
        return None
    if stage == "count":
        return "bean"
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    hue = float(np.median(hsv[:, :, 0]))
    saturation = float(np.median(hsv[:, :, 1]))
    value = float(np.median(hsv[:, :, 2]))
    if stage == "roasted":
        if _has_hole(hsv[:, :, 2]):
            return "insect"
        if value < 50:
            return "burnt"
        if 35 <= hue <= 95 and saturation > 40:
            return "mould"
        if value > 160 and saturation < 90:
            return "quaker"
        return "good"
    if value < 55:
        return "black"
    if circularity < 0.55:
        return "broken"
    if saturation < 45 and value > 150:
        return "fade"
    if 18 <= hue <= 38 and saturation > 80:
        return "sour"
    return "good"


def _has_hole(value: np.ndarray) -> bool:
    """A dark pit inside a lighter bean. A bean that is dark all over is burnt, not bored."""
    height, width = value.shape[:2]
    if height < 12 or width < 12:
        return False
    y1, y2 = int(height * 0.40), max(int(height * 0.40) + 1, int(height * 0.60))
    x1, x2 = int(width * 0.40), max(int(width * 0.40) + 1, int(width * 0.60))
    centre = value[y1:y2, x1:x2]
    if centre.size == 0 or float(centre.mean()) > 50:
        return False
    bean = value < 160
    bean[y1:y2, x1:x2] = False
    ring = value[bean]
    if ring.size < 8:
        return False
    return float(ring.mean()) > float(centre.mean()) + 40


class OnnxCoffeeDetector:
    """coffee.onnx. Accepts Nx6 rows, or an Ultralytics YOLO head with the nine class ids."""

    name = "coffee-line"
    version = "onnx"

    def __init__(self, path: str, providers: list[str], threads: int = 2):
        from app.detectors import onnx_session

        self.session = onnx_session(path, providers, threads)
        self.input_name = self.session.get_inputs()[0].name
        shape = self.session.get_inputs()[0].shape
        self.input_h = int(shape[2]) if isinstance(shape[2], int) else 640
        self.input_w = int(shape[3]) if isinstance(shape[3], int) else 640
        self._letterbox: bool | None = None

    def detect(self, frame, zones: list[dict], now: float, hold: bool) -> list[dict]:
        del now, hold
        letterbox = bool(self._letterbox)
        output, gain, pad_x, pad_y = self._infer(frame, letterbox)
        if self._letterbox is None:
            self._letterbox = _is_yolo_head(output)
            if self._letterbox:
                output, gain, pad_x, pad_y = self._infer(frame, True)
        height, width = frame.shape[:2]
        found = []
        for zone in zones:
            stage = stage_of(zone.get("zone_type"))
            polygon = zone.get("polygon") or []
            if stage is None or len(polygon) < 3:
                continue
            beans = beans_from_onnx_output(
                output, stage, width, height, self.input_w, self.input_h, pad_x, pad_y, gain
            )
            for bean in beans:
                if point_in_polygon(polygon, bean["cx"], bean["cy"]):
                    found.append(bean)
        return found

    def _infer(self, frame: np.ndarray, letterbox: bool):
        image, gain, pad_x, pad_y = _model_canvas(frame, self.input_w, self.input_h, letterbox)
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        tensor = np.transpose(rgb, (2, 0, 1))[None, :, :, :]
        output = np.asarray(self.session.run(None, {self.input_name: tensor})[0])
        return output, gain, pad_x, pad_y


def _is_yolo_head(output) -> bool:
    rows = np.squeeze(np.asarray(output))
    return rows.ndim == 2 and (rows.shape[0] == YOLO_CHANNELS or rows.shape[1] == YOLO_CHANNELS)


def _model_canvas(frame: np.ndarray, input_w: int, input_h: int, letterbox: bool):
    if not letterbox:
        return cv2.resize(frame, (input_w, input_h)), 1.0, 0.0, 0.0
    height, width = frame.shape[:2]
    gain = min(input_w / max(width, 1), input_h / max(height, 1))
    resized = cv2.resize(frame, (max(int(round(width * gain)), 1), max(int(round(height * gain)), 1)))
    canvas = np.full((input_h, input_w, 3), 114, dtype=np.uint8)
    pad_x = (input_w - resized.shape[1]) // 2
    pad_y = (input_h - resized.shape[0]) // 2
    canvas[pad_y : pad_y + resized.shape[0], pad_x : pad_x + resized.shape[1]] = resized
    return canvas, gain, float(pad_x), float(pad_y)


def build_coffee_detector(mode: str, model_path: str, device: str, threads: int = 2):
    if mode.upper() == "DEMO":
        return DemoCoffeeDetector()
    path = Path(model_path) / "coffee.onnx"
    if path.exists():
        from app.detectors import providers_for

        return OnnxCoffeeDetector(str(path), providers_for(device), threads)
    return BlobCoffeeDetector()
