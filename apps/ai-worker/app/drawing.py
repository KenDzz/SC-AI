import cv2
import numpy as np

ZONE_COLORS = {
    "RESTRICTED_AREA": (40, 70, 210),
    "MACHINE_DANGER_ZONE": (30, 30, 180),
    "FORKLIFT_LANE": (20, 140, 220),
    "PRODUCTION_ZONE": (160, 110, 20),
    "PACKING_ZONE": (80, 140, 40),
}

HAIRNET_TEXT = {"YES": "Hairnet: Yes", "NO": "Hairnet: No", "UNKNOWN": "Hairnet: Unknown"}
UNIFORM_TEXT = {
    "CORRECT": "Uniform: Correct",
    "INCORRECT": "Uniform: Incorrect",
    "UNKNOWN": "Uniform: Unknown",
}


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


def annotate(image: np.ndarray, zones: list[dict], tracks: list[dict]) -> np.ndarray:
    canvas = image.copy()
    height, width = canvas.shape[:2]
    for zone in zones:
        points = zone.get("polygon") or []
        if len(points) < 3:
            continue
        contour = np.array([[int(x * width), int(y * height)] for x, y in points], dtype=np.int32)
        color = ZONE_COLORS.get(zone.get("zone_type"), (80, 80, 80))
        overlay = canvas.copy()
        cv2.fillPoly(overlay, [contour], color)
        cv2.addWeighted(overlay, 0.18, canvas, 0.82, 0, canvas)
        cv2.polylines(canvas, [contour], True, color, 2)
        label_at = contour[0]
        _label(canvas, zone.get("name") or zone.get("zone_type") or "Zone", int(label_at[0]), int(label_at[1]) - 6, color)
    for track in tracks:
        x1, y1, x2, y2 = [int(v) for v in track["bbox_xyxy"]]
        person = track.get("class_name") == "person"
        violated = track.get("hairnet") == "NO" or track.get("uniform") == "INCORRECT"
        color = (40, 60, 200) if person and violated else ((40, 140, 70) if person else (30, 130, 230))
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)
        if person:
            lines = [
                f"Person {track['track_id']}",
                HAIRNET_TEXT.get(track.get("hairnet"), "Hairnet: Unknown"),
                UNIFORM_TEXT.get(track.get("uniform"), "Uniform: Unknown"),
            ]
        else:
            lines = [f"Forklift {track['track_id']}"]
        for offset, text in enumerate(lines):
            _label(canvas, text, x1, y1 - 8 - (len(lines) - 1 - offset) * 18, color)
    return canvas


def _label(image: np.ndarray, text: str, x: int, y: int, color: tuple[int, int, int]) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.45
    (width, height), _ = cv2.getTextSize(text, font, scale, 1)
    y = max(height + 4, y)
    x = max(0, x)
    cv2.rectangle(image, (x, y - height - 6), (x + width + 8, y + 4), color, -1)
    cv2.putText(image, text, (x + 4, y - 2), font, scale, (255, 255, 255), 1, cv2.LINE_AA)
