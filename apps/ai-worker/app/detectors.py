"""Model adapters.

DEMO_MODE uses scripted detections so the workflow can be shown without weights.
REAL_AI_MODE uses the OpenCV HOG person detector (shipped with OpenCV, Apache-2.0)
unless an ONNX file with the documented Nx6 contract is mounted.
"""

from pathlib import Path

import cv2
import numpy as np

from app.scenes import scripted_objects

PERSON_CLASS = 0
FORKLIFT_CLASS = 1


def _box(nx: float, ny: float, width: int, height: int, bw: float, bh: float) -> list[float]:
    x1 = max(0.0, nx - bw / 2) * width
    y1 = max(0.0, ny - bh / 2) * height
    x2 = min(1.0, nx + bw / 2) * width
    y2 = min(1.0, ny + bh / 2) * height
    return [x1, y1, x2, y2]


class DemoDetector:
    def detect(self, frame, zones: list[dict], now: float, hold_inside: bool) -> list[dict]:
        height, width = frame.shape[:2]
        detections = []
        for item in scripted_objects(zones, now, hold_inside):
            forklift = item["class_name"] == "forklift"
            detections.append(
                {
                    "class_name": item["class_name"],
                    "class_id": FORKLIFT_CLASS if forklift else PERSON_CLASS,
                    "confidence": 0.93 if forklift else 0.9,
                    "bbox_xyxy": _box(item["nx"], item["ny"], width, height, 0.14 if forklift else 0.08, 0.16 if forklift else 0.24),
                    "ppe_mode": item["ppe_mode"],
                }
            )
        return detections


class HogPersonDetector:
    def __init__(self):
        self.hog = cv2.HOGDescriptor()
        self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    def detect(self, frame, zones: list[dict], now: float, hold_inside: bool) -> list[dict]:
        del zones, now, hold_inside
        scale = 640.0 / max(frame.shape[1], 1)
        small = cv2.resize(frame, (640, max(64, int(frame.shape[0] * scale))))
        rects, weights = self.hog.detectMultiScale(small, hitThreshold=0.2, winStride=(8, 8), padding=(8, 8), scale=1.05)
        inverse = 1.0 / scale
        detections = []
        for (x, y, w, h), weight in zip(rects, weights):
            box = [x * inverse, y * inverse, (x + w) * inverse, (y + h) * inverse]
            if not _box_has_head(frame, box):
                continue
            detections.append(
                {
                    "class_name": "person",
                    "class_id": PERSON_CLASS,
                    "confidence": float(min(0.99, max(0.35, weight))),
                    "bbox_xyxy": box,
                    "ppe_mode": "model",
                }
            )
        return detections


class FactoryPersonDetector:
    """A worker is a light hairnet, or a patch of hair, directly above a face and a uniform."""

    def detect(self, frame, zones: list[dict], now: float, hold_inside: bool) -> list[dict]:
        del zones, now, hold_inside
        return _nms(_people_from_heads(frame), 0.35)


class OnnxObjectDetector:
    """ONNX contract: one output tensor of shape Nx6 or 1xNx6.

    Columns are x1, y1, x2, y2, score, class_id in the model's input pixel space.
    class_id 0 is person and class_id 1 is forklift.
    """

    def __init__(self, path: str, providers: list[str]):
        import onnxruntime as ort

        self.session = ort.InferenceSession(str(path), providers=providers)
        self.input_name = self.session.get_inputs()[0].name
        shape = self.session.get_inputs()[0].shape
        self.input_h = int(shape[2]) if isinstance(shape[2], int) else 640
        self.input_w = int(shape[3]) if isinstance(shape[3], int) else 640

    def detect(self, frame, zones: list[dict], now: float, hold_inside: bool) -> list[dict]:
        del zones, now, hold_inside
        resized = cv2.resize(frame, (self.input_w, self.input_h))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        tensor = np.transpose(rgb, (2, 0, 1))[None, :, :, :]
        output = np.asarray(self.session.run(None, {self.input_name: tensor})[0])
        if output.ndim == 3:
            output = output[0]
        if output.ndim != 2 or output.shape[1] < 6:
            raise ValueError(f"Unsupported ONNX output shape {output.shape}. Expected Nx6.")
        sx = frame.shape[1] / self.input_w
        sy = frame.shape[0] / self.input_h
        detections = []
        for row in output:
            score = float(row[4])
            if score < 0.35:
                continue
            class_id = int(row[5])
            name = {0: "person", 1: "forklift"}.get(class_id)
            if name is None:
                continue
            detections.append(
                {
                    "class_name": name,
                    "class_id": class_id,
                    "confidence": score,
                    "bbox_xyxy": [float(row[0]) * sx, float(row[1]) * sy, float(row[2]) * sx, float(row[3]) * sy],
                    "ppe_mode": "model",
                }
            )
        return detections


class DemoPPEClassifier:
    def classify(self, crop, context: dict | None = None) -> dict:
        del crop
        context = context or {}
        if context.get("ppe_mode") == "unknown":
            return {"hairnet": "UNKNOWN", "uniform": "UNKNOWN", "confidence": 0.41}
        zone_types = context.get("zone_types") or []
        hairnet = "NO" if "PACKING_ZONE" in zone_types else "YES"
        uniform = "INCORRECT" if "PRODUCTION_ZONE" in zone_types else "CORRECT"
        confidence = 0.84 if hairnet == "NO" or uniform == "INCORRECT" else 0.9
        return {"hairnet": hairnet, "uniform": uniform, "confidence": confidence}


class UnknownPPEClassifier:
    def classify(self, crop, context: dict | None = None) -> dict:
        del crop, context
        return {"hairnet": "UNKNOWN", "uniform": "UNKNOWN", "confidence": 0.0}


class ColorPPEClassifier:
    """Reads the head and torso of a person crop.

    A light or blue cap is a hairnet. Dark or brown hair with no cap is missing.
    A beige, white, or blue work shirt is a correct uniform. A strong red or pink
    shirt is incorrect. Anything unclear stays UNKNOWN.
    """

    def classify(self, crop, context: dict | None = None) -> dict:
        del context
        if crop is None or getattr(crop, "size", 0) == 0 or crop.shape[0] < 72 or crop.shape[1] < 28:
            return {"hairnet": "UNKNOWN", "uniform": "UNKNOWN", "confidence": 0.0}
        height, width = crop.shape[:2]
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        top = crop[: max(6, int(height * 0.12))]
        head = top[:, int(top.shape[1] * 0.30) : int(top.shape[1] * 0.70)]
        torso = hsv[int(height * 0.30) : int(height * 0.70), int(width * 0.22) : int(width * 0.78)]
        hairnet, hairnet_confidence = _hairnet_from_head(head)
        uniform, uniform_confidence = _uniform_from_torso(torso)
        return {
            "hairnet": hairnet,
            "uniform": uniform,
            "confidence": round(max(hairnet_confidence, uniform_confidence), 3),
        }


def _cap_patch(top: np.ndarray) -> np.ndarray:
    if top.size == 0:
        return top
    hsv = cv2.cvtColor(top, cv2.COLOR_BGR2HSV)
    hue, sat, val = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    skin = (hue > 3) & (hue < 25) & (sat > 30) & (sat < 170) & (val > 120)
    bright = (sat < 75) & (val > 140) & ~skin
    columns = np.where(bright.any(axis=0))[0]
    if len(columns) < 4:
        return top
    groups = []
    start = previous = int(columns[0])
    for column in columns[1:]:
        column = int(column)
        if column > previous + 4:
            groups.append((start, previous))
            start = column
        previous = column
    groups.append((start, previous))
    best_start, best_end = max(groups, key=lambda group: int(bright[:, group[0] : group[1] + 1].sum()))
    return top[:, best_start : best_end + 1]


def _hairnet_from_head(head: np.ndarray) -> tuple[str, float]:
    if head.size == 0:
        return "UNKNOWN", 0.0
    hsv = cv2.cvtColor(head, cv2.COLOR_BGR2HSV)
    hue, sat, val = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    skin = (hue > 3) & (hue < 25) & (sat > 30) & (sat < 170) & (val > 120)
    cap = ((sat < 75) & (val > 150) & ~skin) | ((hue > 90) & (hue < 130) & (sat > 35) & (val > 80))
    hair = (val < 80) & ~skin & ~cap
    cap_fraction = float(cap.mean())
    hair_fraction = float(hair.mean())
    if cap_fraction < 0.08 and hair_fraction >= 0.4:
        return "NO", min(0.9, 0.55 + hair_fraction * 0.4)
    return _pick(cap_fraction, hair_fraction, "YES", "NO")


def _uniform_from_torso(torso: np.ndarray) -> tuple[str, float]:
    if torso.size == 0:
        return "UNKNOWN", 0.0
    hue, sat, val = torso[:, :, 0], torso[:, :, 1], torso[:, :, 2]
    workwear = (
        ((hue > 10) & (hue < 35) & (sat > 15) & (sat < 120) & (val > 100) & (val < 220))
        | ((sat < 45) & (val > 185))
        | ((hue > 95) & (hue < 130) & (sat > 45) & (val > 50))
    )
    casual = ((hue < 10) | (hue > 165)) & (sat > 90) & (val > 70)
    return _pick(float(workwear.mean()), float(casual.mean()), "CORRECT", "INCORRECT")


def _pick(positive: float, negative: float, yes_label: str, no_label: str) -> tuple[str, float]:
    if positive >= 0.28 and positive >= negative + 0.10:
        return yes_label, min(0.9, 0.55 + positive * 0.4)
    if negative >= 0.22 and negative >= positive + 0.10:
        return no_label, min(0.9, 0.55 + negative * 0.4)
    return "UNKNOWN", 0.0


class OnnxPPEClassifier:
    """ONNX contract: 128x128 RGB input, output shape (1, 6).

    Logits are hairnet YES/NO/UNKNOWN then uniform CORRECT/INCORRECT/UNKNOWN.
    """

    def __init__(self, path: str, providers: list[str]):
        import onnxruntime as ort

        self.session = ort.InferenceSession(str(path), providers=providers)
        self.input_name = self.session.get_inputs()[0].name

    def classify(self, crop, context: dict | None = None) -> dict:
        del context
        if crop is None or crop.size == 0:
            return {"hairnet": "UNKNOWN", "uniform": "UNKNOWN", "confidence": 0.0}
        image = cv2.resize(crop, (128, 128))
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        tensor = np.transpose(rgb, (2, 0, 1))[None, :, :, :]
        logits = np.asarray(self.session.run(None, {self.input_name: tensor})[0]).reshape(-1)
        if logits.shape[0] < 6:
            return {"hairnet": "UNKNOWN", "uniform": "UNKNOWN", "confidence": 0.0}
        hairnet = ["YES", "NO", "UNKNOWN"][int(np.argmax(logits[0:3]))]
        uniform = ["CORRECT", "INCORRECT", "UNKNOWN"][int(np.argmax(logits[3:6]))]
        confidence = float(max(_softmax(logits[0:3]).max(), _softmax(logits[3:6]).max()))
        return {"hairnet": hairnet, "uniform": uniform, "confidence": confidence}


def _box_has_head(frame, box: list[float]) -> bool:
    height, width = frame.shape[:2]
    x1, y1, x2, y2 = [int(max(0, v)) for v in box[:2]] + [int(min(width, box[2])), int(min(height, box[3]))]
    if y2 - y1 < 48 or x2 - x1 < 20:
        return False
    if (y2 - y1) < (x2 - x1) * 1.05:
        return False
    head = frame[y1 : y1 + max(8, int((y2 - y1) * 0.38)), x1 + int((x2 - x1) * 0.2) : x2 - int((x2 - x1) * 0.2)]
    skin, cap, hair = _head_masks(head)
    if skin.size == 0:
        return False
    return float(skin.mean()) > 0.08 and (float(cap.mean()) > 0.08 or float(hair.mean()) > 0.12 or float(skin.mean()) > 0.16)


def _people_from_heads(frame) -> list[dict]:
    height, width = frame.shape[:2]
    skin, cap, hair = _head_masks(frame)
    found = _blobs_to_people(frame, cap, skin, 0.86)
    found.extend(_blobs_to_people(frame, hair, skin, 0.74))
    found = _keep_upper_heads(found, width)
    for person in found:
        box = person["bbox_xyxy"]
        box[0] = max(0, box[0])
        box[1] = max(0, box[1])
        box[2] = min(width - 1, box[2])
        box[3] = min(height - 1, box[3])
    return found


def _blobs_to_people(frame, feature_mask: np.ndarray, skin: np.ndarray, confidence: float) -> list[dict]:
    height, width = frame.shape[:2]
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    hue, sat, val = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    uniform = (
        ((hue > 8) & (hue < 35) & (sat > 18) & (sat < 150) & (val > 80))
        | ((sat < 55) & (val > 170))
        | ((hue > 95) & (hue < 135) & (sat > 35) & (val > 35))
    )
    mask = cv2.morphologyEx(feature_mask.astype(np.uint8) * 255, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    people = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if h < height * 0.035 or h > height * 0.13 or w > width * 0.1 or w > h * 2.4:
            continue
        if y < height * 0.03:
            continue
        top = y
        above = feature_mask[max(0, y - int(h * 2.2)) : y, x : x + w]
        if above.size and above.any():
            rows = above.any(axis=1)
            top = max(0, y - int(h * 2.2)) + int(np.argmax(rows))
        face_y1, face_y2 = y + h, min(height, y + h + int(h * 1.15))
        face_x1, face_x2 = x + w // 8, max(x + w // 8 + 1, x + w - w // 8)
        face = skin[face_y1:face_y2, face_x1:face_x2]
        face_values = val[face_y1:face_y2, face_x1:face_x2]
        if face.size == 0 or float(face.mean()) < 0.2 or float(face_values.std()) < 12:
            continue
        column_x1, column_x2 = max(0, x - w // 2), min(width, x + w + w // 2)
        bottom = face_y2
        while bottom < height - 4 and bottom - y < height * 0.7:
            band = uniform[bottom : bottom + 4, column_x1:column_x2]
            if band.size == 0 or float(band.mean()) < 0.22:
                break
            bottom += 4
        if bottom - face_y2 < h * 1.6:
            continue
        body_height = bottom - top
        body_width = max(w * 2.2, body_height * 0.42)
        center_x = x + w / 2
        body_x1 = max(0, int(center_x - body_width / 2))
        body_x2 = min(width - 1, int(center_x + body_width / 2))
        box_w, box_h = body_x2 - body_x1, body_height
        if box_w > width * 0.34 or not (height * 0.28 <= box_h <= height * 0.72):
            continue
        body_bottom = min(height - 1, bottom)
        people.append(
            {
                "class_name": "person",
                "class_id": PERSON_CLASS,
                "confidence": confidence,
                "bbox_xyxy": [float(body_x1), float(top), float(body_x2), float(body_bottom)],
                "ppe_mode": "model",
            }
        )
    return people


def _keep_upper_heads(people: list[dict], width: int) -> list[dict]:
    kept = []
    for person in sorted(people, key=lambda item: item["bbox_xyxy"][1]):
        center = (person["bbox_xyxy"][0] + person["bbox_xyxy"][2]) / 2
        top = person["bbox_xyxy"][1]
        covered = False
        for other in kept:
            other_center = (other["bbox_xyxy"][0] + other["bbox_xyxy"][2]) / 2
            if abs(center - other_center) < width * 0.14 and other["bbox_xyxy"][1] <= top:
                covered = True
                break
        if not covered:
            kept.append(person)
    return kept


def _head_masks(image: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if image.size == 0:
        empty = np.zeros((0, 0), dtype=bool)
        return empty, empty, empty
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hue, sat, val = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    skin = (hue > 3) & (hue < 22) & (sat > 35) & (sat < 180) & (val > 70)
    cap = (sat < 55) & (val > 168) & ~skin
    hair = (val < 65) & ~skin
    return skin, cap, hair


def _nms(detections: list[dict], threshold: float) -> list[dict]:
    ordered = sorted(detections, key=lambda item: item["bbox_xyxy"][3] - item["bbox_xyxy"][1], reverse=True)
    kept = []
    for detection in ordered:
        if all(_iou(detection["bbox_xyxy"], other["bbox_xyxy"]) < threshold for other in kept):
            kept.append(detection)
    return kept


def _iou(a: list[float], b: list[float]) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1]) + max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1]) - inter
    return inter / area if area else 0.0


def _softmax(values: np.ndarray) -> np.ndarray:
    shifted = values - np.max(values)
    exp = np.exp(shifted)
    return exp / max(exp.sum(), 1e-6)


def providers_for(device: str) -> list[str]:
    if device.lower() in {"cuda", "gpu"}:
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]
    return ["CPUExecutionProvider"]


class YoloxPersonDetector:
    """YOLOX-Nano, Apache-2.0. Output is decoded from the 416-pixel grid."""

    def __init__(self, path: str, providers: list[str]):
        import onnxruntime as ort

        self.session = ort.InferenceSession(str(path), providers=providers)
        self.input_name = self.session.get_inputs()[0].name
        self.input_size = 416

    def detect(self, frame, zones: list[dict], now: float, hold_inside: bool) -> list[dict]:
        del zones, now, hold_inside
        height, width = frame.shape[:2]
        canvas, scale, pad_x, pad_y = _letterbox(frame, self.input_size)
        tensor = np.transpose(canvas, (2, 0, 1))[None, :, :, :]
        output = np.asarray(self.session.run(None, {self.input_name: tensor})[0])[0]
        detections = []
        offset = 0
        for stride in (8, 16, 32):
            grid = self.input_size // stride
            count = grid * grid
            feature = output[offset : offset + count]
            offset += count
            gy, gx = np.meshgrid(np.arange(grid), np.arange(grid), indexing="ij")
            gx = gx.reshape(-1)
            gy = gy.reshape(-1)
            center_x = (feature[:, 0] + gx) * stride
            center_y = (feature[:, 1] + gy) * stride
            box_w = np.exp(np.clip(feature[:, 2], -6, 6)) * stride
            box_h = np.exp(np.clip(feature[:, 3], -6, 6)) * stride
            score = feature[:, 4] * feature[:, 5]
            for index in np.where(score > 0.35)[0]:
                x1 = (center_x[index] - box_w[index] / 2 - pad_x) / scale
                y1 = (center_y[index] - box_h[index] / 2 - pad_y) / scale
                x2 = (center_x[index] + box_w[index] / 2 - pad_x) / scale
                y2 = (center_y[index] + box_h[index] / 2 - pad_y) / scale
                detections.append(
                    {
                        "class_name": "person",
                        "class_id": PERSON_CLASS,
                        "confidence": float(score[index]),
                        "bbox_xyxy": [
                            float(np.clip(x1, 0, width - 1)),
                            float(np.clip(y1, 0, height - 1)),
                            float(np.clip(x2, 0, width - 1)),
                            float(np.clip(y2, 0, height - 1)),
                        ],
                        "ppe_mode": "model",
                    }
                )
        return _nms(detections, 0.45)


def _letterbox(frame: np.ndarray, size: int) -> tuple[np.ndarray, float, int, int]:
    height, width = frame.shape[:2]
    scale = min(size / width, size / height)
    resized = cv2.resize(frame, (int(width * scale), int(height * scale)))
    canvas = np.full((size, size, 3), 114, dtype=np.float32)
    pad_x = (size - resized.shape[1]) // 2
    pad_y = (size - resized.shape[0]) // 2
    canvas[pad_y : pad_y + resized.shape[0], pad_x : pad_x + resized.shape[1]] = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    return canvas, scale, pad_x, pad_y


def build_detectors(mode: str, model_path: str, device: str):
    root = Path(model_path)
    providers = providers_for(device)
    person_onnx = root / "person.onnx"
    forklift_onnx = root / "forklift.onnx"
    ppe_onnx = root / "ppe.onnx"
    person_name, person_version = "person-detector", "hog-v1"
    if mode.upper() == "DEMO":
        detector = DemoDetector()
        ppe = DemoPPEClassifier()
        return detector, ppe, "person-detector", "v0-demo", "ppe-classifier", "v0.1-demo"
    if person_onnx.exists():
        detector = YoloxPersonDetector(str(person_onnx), providers)
        person_name, person_version = "yolox-nano", "apache-2.0"
    else:
        detector = FactoryPersonDetector()
        person_version = "factory-head-v1"
    if forklift_onnx.exists() and not isinstance(detector, OnnxObjectDetector):
        # A dedicated forklift file is used by wrapping both detectors below.
        pass
    ppe_name, ppe_version = "ppe-classifier", "unloaded"
    if ppe_onnx.exists():
        ppe = OnnxPPEClassifier(str(ppe_onnx), providers)
        ppe_version = "onnx"
    else:
        ppe = ColorPPEClassifier()
        ppe_version = "color-v1"
    if forklift_onnx.exists():
        detector = _ForkliftUnion(detector, OnnxObjectDetector(str(forklift_onnx), providers))
    return detector, ppe, person_name, person_version, ppe_name, ppe_version


class _ForkliftUnion:
    def __init__(self, person_detector, forklift_detector):
        self.person_detector = person_detector
        self.forklift_detector = forklift_detector

    def detect(self, frame, zones, now, hold_inside):
        people = [item for item in self.person_detector.detect(frame, zones, now, hold_inside) if item["class_name"] == "person"]
        trucks = [item for item in self.forklift_detector.detect(frame, zones, now, hold_inside) if item["class_name"] == "forklift"]
        return people + trucks
