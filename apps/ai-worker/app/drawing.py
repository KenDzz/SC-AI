import cv2
import numpy as np

ZONE_COLORS = {
    "RESTRICTED_AREA": (40, 70, 210),
    "MACHINE_DANGER_ZONE": (30, 30, 180),
    "FORKLIFT_LANE": (20, 140, 220),
    "PRODUCTION_ZONE": (160, 110, 20),
    "PACKING_ZONE": (80, 140, 40),
    "GREEN_COFFEE_LINE": (50, 130, 40),
    "ROASTED_COFFEE_LINE": (40, 80, 140),
    "COFFEE_COUNT_LINE": (140, 120, 30),
}

COFFEE_ZONES = {"GREEN_COFFEE_LINE", "ROASTED_COFFEE_LINE", "COFFEE_COUNT_LINE"}
BEAN_COLORS = {
    "good": (50, 140, 40),
    "bean": (150, 120, 30),
    "black": (30, 30, 30),
    "broken": (40, 80, 200),
    "fade": (170, 170, 160),
    "sour": (40, 190, 220),
    "quaker": (150, 180, 200),
    "burnt": (20, 20, 60),
    "insect": (30, 50, 170),
    "mould": (70, 150, 30),
}

CHECK_COLORS = {
    "violation": (40, 60, 200),
    "unknown": (120, 120, 120),
    "ok": (40, 140, 70),
}
NO_RULE_COLOR = (150, 110, 60)
FORKLIFT_COLOR = (30, 130, 230)


def track_color(track: dict) -> tuple[int, int, int]:
    """A person takes the colour of their worst rule check; with no rule in play they stay neutral."""
    if track.get("class_name") != "person":
        return FORKLIFT_COLOR
    states = {check.get("state") for check in track.get("checks") or []}
    for state in ("violation", "unknown", "ok"):
        if state in states:
            return CHECK_COLORS[state]
    return NO_RULE_COLOR


def synthetic_frame(width: int, height: int, title: str) -> np.ndarray:
    image = np.zeros((height, width, 3), dtype=np.uint8)
    image[:] = (196, 202, 206)
    cv2.rectangle(image, (0, int(height * 0.62)), (width, height), (176, 182, 186), -1)
    cv2.putText(image, title, (20, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (45, 52, 58), 2, cv2.LINE_AA)
    return image


def jpeg_bytes(image: np.ndarray, quality: int = 70) -> bytes:
    ok, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        return b""
    return encoded.tobytes()


def annotate(image: np.ndarray, zones: list[dict], tracks: list[dict], beans: list[dict] | None = None, coffee: list[dict] | None = None) -> np.ndarray:
    canvas = image.copy()
    height, width = canvas.shape[:2]
    reports = {item.get("zone_id"): item for item in coffee or []}
    for zone in zones:
        name = zone.get("name") or zone.get("zone_type") or "Zone"
        points = zone.get("polygon") or []
        if len(points) < 3:
            # A paused zone has no place in this view, so it is not drawn. The camera page lists it.
            continue
        contour = np.array([[int(x * width), int(y * height)] for x, y in points], dtype=np.int32)
        color = ZONE_COLORS.get(zone.get("zone_type"), (80, 80, 80))
        overlay = canvas.copy()
        cv2.fillPoly(overlay, [contour], color)
        cv2.addWeighted(overlay, 0.18, canvas, 0.82, 0, canvas)
        cv2.polylines(canvas, [contour], True, color, 2)
        if zone.get("zone_type") in COFFEE_ZONES:
            ys = [point[1] for point in points]
            xs = [point[0] for point in points]
            line_y = int(((min(ys) + max(ys)) / 2) * height)
            cv2.line(canvas, (int(min(xs) * width), line_y), (int(max(xs) * width), line_y), color, 1, cv2.LINE_AA)
        label_at = contour[0]
        suffix = " (auto-aligned)" if zone.get("view_state") == "SHIFTED" else ""
        report = reports.get(zone.get("id"))
        if report:
            if report.get("stage") == "count":
                suffix += f" · {report.get('total', 0)} beans"
            else:
                suffix += f" · {report.get('total', 0)} beans, {round(float(report.get('defect_rate') or 0) * 100)}% defects"
        _label(canvas, name + suffix, int(label_at[0]), int(label_at[1]) - 6, color)
    for track in tracks:
        x1, y1, x2, y2 = [int(v) for v in track["bbox_xyxy"]]
        color = track_color(track)
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)
        if track.get("class_name") == "person":
            lines = [f"Person {track['track_id']}"] + [check["text"] for check in track.get("checks") or []]
        else:
            lines = [f"Forklift {track['track_id']}"]
        for offset, text in enumerate(lines):
            _label(canvas, text, x1, y1 - 8 - (len(lines) - 1 - offset) * 18, color)
    for bean in beans or []:
        x1, y1, x2, y2 = [int(v) for v in bean["bbox_xyxy"]]
        color = BEAN_COLORS.get(bean.get("class_name"), (80, 80, 80))
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)
        _label(canvas, str(bean.get("class_name") or "bean"), x1, y1 - 6, color)
    return canvas


def _label(image: np.ndarray, text: str, x: int, y: int, color: tuple[int, int, int]) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.45
    (width, height), _ = cv2.getTextSize(text, font, scale, 1)
    y = max(height + 4, y)
    x = max(0, min(x, image.shape[1] - width - 8))
    cv2.rectangle(image, (x, y - height - 6), (x + width + 8, y + 4), color, -1)
    cv2.putText(image, text, (x + 4, y - 2), font, scale, (255, 255, 255), 1, cv2.LINE_AA)
