"""Keeps zones on the floor when the camera view moves.

Each zone remembers the frame it was drawn on. About once a second the worker
matches the live frame against that reference with ORB features and a RANSAC
homography. A small move shifts the zone by the measured homography. A view
that no longer matches, or a zone pushed out of the frame, pauses the zone until
the view matches again. Zones without a reference frame are used as drawn.

A camera marked multi-view moves between views, such as PTZ presets. Zones locked
to the same frame form one view, and only the view that matches the live frame
best is used; the others are hidden until the camera returns to them.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Callable

import cv2
import numpy as np
from shapely.geometry import Polygon, box

log = logging.getLogger("worker.alignment")

ALIGNED = "ALIGNED"
SHIFTED = "SHIFTED"
OUT_OF_VIEW = "OUT_OF_VIEW"
VIEW_CHANGED = "VIEW_CHANGED"
UNVERIFIED = "UNVERIFIED"
OTHER_VIEW = "OTHER_VIEW"
PAUSED = {OUT_OF_VIEW, VIEW_CHANGED}

MIN_INLIERS = 25
STILL_PCT = 1.0
MAX_SHIFT_PCT = 20.0
MIN_VISIBLE = 0.6
CHECK_EVERY_S = 1.0
CONFIRM_CHECKS = 2
RETRY_MISSING_S = 30.0
SWITCH_RATIO = 1.25


@dataclass
class ZoneView:
    state: str
    polygon: list[list[float]] | None
    shift_pct: float = 0.0


@dataclass
class Measurement:
    state: str
    homography: np.ndarray | None
    shift_pct: float
    inliers: int = 0


class Reference:
    def __init__(self, image: np.ndarray):
        self.size = (image.shape[1], image.shape[0])
        self.keypoints, self.descriptors = _features(image)


def _features(image: np.ndarray):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    return cv2.ORB_create(1500).detectAndCompute(gray, None)


def measure(reference: Reference, frame: np.ndarray, frame_features=None) -> Measurement:
    """Homography from reference pixels to frame pixels, and what it means for the zones."""
    height, width = frame.shape[:2]
    keypoints, descriptors = frame_features or _features(frame)
    if reference.descriptors is None or descriptors is None or len(keypoints) < MIN_INLIERS:
        return Measurement(VIEW_CHANGED, None, 0.0)
    pairs = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(reference.descriptors, descriptors, k=2)
    good = [first for first, second in (pair for pair in pairs if len(pair) == 2) if first.distance < 0.75 * second.distance]
    if len(good) < MIN_INLIERS:
        return Measurement(VIEW_CHANGED, None, 0.0)
    sx, sy = width / reference.size[0], height / reference.size[1]
    source = np.float32([(reference.keypoints[m.queryIdx].pt[0] * sx, reference.keypoints[m.queryIdx].pt[1] * sy) for m in good])
    target = np.float32([keypoints[m.trainIdx].pt for m in good])
    homography, mask = cv2.findHomography(source, target, cv2.RANSAC, 4.0)
    inliers = int(mask.sum()) if mask is not None else 0
    if homography is None or inliers < MIN_INLIERS:
        return Measurement(VIEW_CHANGED, None, 0.0, inliers)
    scale = abs(float(np.linalg.det(homography[:2, :2])))
    if not 0.25 <= scale <= 4.0:
        return Measurement(VIEW_CHANGED, None, 0.0, inliers)
    corners = np.float32([[0, 0], [width, 0], [width, height], [0, height]]).reshape(-1, 1, 2)
    moved = np.linalg.norm(cv2.perspectiveTransform(corners, homography) - corners, axis=2).max()
    shift_pct = float(moved / np.hypot(width, height) * 100.0)
    if shift_pct <= STILL_PCT:
        return Measurement(ALIGNED, None, shift_pct, inliers)
    if shift_pct > MAX_SHIFT_PCT:
        return Measurement(VIEW_CHANGED, None, shift_pct, inliers)
    return Measurement(SHIFTED, homography, shift_pct, inliers)


def project(polygon: list[list[float]], homography: np.ndarray, width: int, height: int) -> tuple[list[list[float]], float]:
    """Moves a normalized polygon with the camera. Returns the new polygon and how much of it is still in frame."""
    points = np.float32([[x * width, y * height] for x, y in polygon]).reshape(-1, 1, 2)
    moved = cv2.perspectiveTransform(points, homography).reshape(-1, 2)
    shifted = [[round(float(x) / width, 5), round(float(y) / height, 5)] for x, y in moved]
    shape = Polygon(shifted)
    if not shape.is_valid:
        shape = shape.buffer(0)
    if shape.is_empty or shape.area <= 0:
        return shifted, 0.0
    return shifted, float(shape.intersection(box(0, 0, 1, 1)).area / shape.area)


@dataclass
class _ReferenceState:
    reference: Reference | None = None
    missing_since: float | None = None
    confirmed: Measurement | None = None
    candidate: str | None = None
    candidate_count: int = 0
    last_check: float = float("-inf")
    last_inliers: int = 0


@dataclass
class ViewAligner:
    load: Callable[[str], bytes | None]
    check_every_s: float = CHECK_EVERY_S
    confirm_checks: int = CONFIRM_CHECKS
    _states: dict[str, _ReferenceState] = field(default_factory=dict)
    _active: str | None = None
    _switch_to: str | None = None
    _switch_count: int = 0

    def update(self, frame: np.ndarray, zones: list[dict], now: float | None = None, multi_view: bool = False) -> dict[str, ZoneView]:
        now = time.time() if now is None else now
        height, width = frame.shape[:2]
        keys = list(dict.fromkeys(zone["reference_key"] for zone in zones if zone.get("reference_key")))
        frame_features = None
        checked = False
        for key in keys:
            state = self._states.setdefault(key, _ReferenceState())
            if now - state.last_check < self.check_every_s:
                continue
            state.last_check = now
            if not self._ensure_reference(key, state, now):
                continue
            if frame_features is None:
                frame_features = _features(frame)
            measured = measure(state.reference, frame, frame_features)
            state.last_inliers = measured.inliers
            self._settle(state, measured)
            checked = True
        for key in set(self._states) - set(keys):
            self._states.pop(key, None)
        if not multi_view:
            self._active, self._switch_to, self._switch_count = None, None, 0
        elif checked:
            self._pick_view(keys)
        views: dict[str, ZoneView] = {}
        for zone in zones:
            key = zone.get("reference_key")
            polygon = zone.get("polygon") or []
            if not key:
                views[zone["id"]] = ZoneView(UNVERIFIED, polygon)
                continue
            state = self._states[key]
            if multi_view and self._active is not None and key != self._active and state.confirmed is not None:
                views[zone["id"]] = ZoneView(OTHER_VIEW, None)
                continue
            views[zone["id"]] = self._view(state, polygon, width, height)
        return views

    def _pick_view(self, keys: list[str]) -> None:
        """Keeps the current view until another one matches clearly better twice in a row."""
        scores = {
            key: self._states[key].last_inliers
            for key in keys
            if self._states[key].confirmed is not None and self._states[key].confirmed.state not in PAUSED
        }
        if not scores:
            self._active, self._switch_to, self._switch_count = None, None, 0
            return
        best = max(scores, key=scores.get)
        if self._active not in scores:
            self._active, self._switch_to, self._switch_count = best, None, 0
            return
        if best == self._active or scores[best] < SWITCH_RATIO * scores[self._active]:
            self._switch_to, self._switch_count = None, 0
            return
        if self._switch_to == best:
            self._switch_count += 1
        else:
            self._switch_to, self._switch_count = best, 1
        if self._switch_count >= self.confirm_checks:
            self._active, self._switch_to, self._switch_count = best, None, 0

    def _ensure_reference(self, key: str, state: _ReferenceState, now: float) -> bool:
        if state.reference is not None:
            return True
        if state.missing_since is not None and now - state.missing_since < RETRY_MISSING_S:
            return False
        data = self.load(key)
        image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR) if data else None
        if image is None:
            state.missing_since = now
            log.warning("zone reference frame is missing; the zone is used as drawn")
            return False
        state.reference = Reference(image)
        state.missing_since = None
        return True

    def _settle(self, state: _ReferenceState, measured: Measurement) -> None:
        """Pausing or resuming needs the same answer twice in a row; moving an active zone does not."""
        if state.confirmed is None or (state.confirmed.state in PAUSED) == (measured.state in PAUSED):
            state.confirmed = measured
            state.candidate, state.candidate_count = None, 0
            return
        if state.candidate == measured.state:
            state.candidate_count += 1
        else:
            state.candidate, state.candidate_count = measured.state, 1
        if state.candidate_count >= self.confirm_checks:
            state.confirmed = measured
            state.candidate, state.candidate_count = None, 0

    def _view(self, state: _ReferenceState, polygon: list[list[float]], width: int, height: int) -> ZoneView:
        measured = state.confirmed
        if measured is None:
            return ZoneView(UNVERIFIED, polygon)
        if measured.state == VIEW_CHANGED:
            return ZoneView(VIEW_CHANGED, None, round(measured.shift_pct, 2))
        if measured.state == ALIGNED:
            return ZoneView(ALIGNED, polygon, round(measured.shift_pct, 2))
        shifted, visible = project(polygon, measured.homography, width, height)
        if visible < MIN_VISIBLE:
            return ZoneView(OUT_OF_VIEW, None, round(measured.shift_pct, 2))
        return ZoneView(SHIFTED, shifted, round(measured.shift_pct, 2))
