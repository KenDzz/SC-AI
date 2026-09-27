"""ByteTrack via the Apache-2.0 supervision package. Tracking is not implemented here."""

import numpy as np
import supervision as sv

CLASS_IDS = {"person": 0, "forklift": 1}
CLASS_NAMES = {0: "person", 1: "forklift"}


class PersonTracker:
    def __init__(self, frame_rate: int = 5):
        self.tracker = sv.ByteTrack(
            track_activation_threshold=0.2,
            lost_track_buffer=max(int(frame_rate) * 3, 8),
            minimum_matching_threshold=0.7,
            frame_rate=max(int(frame_rate), 1),
            minimum_consecutive_frames=1,
        )

    def update(self, detections: list[dict]) -> list[dict]:
        if not detections:
            empty = sv.Detections(
                xyxy=np.empty((0, 4), dtype=float),
                confidence=np.empty((0,), dtype=float),
                class_id=np.empty((0,), dtype=int),
            )
            return _to_dicts(self.tracker.update_with_detections(empty))
        xyxy = np.array([item["bbox_xyxy"] for item in detections], dtype=float)
        confidence = np.array([item["confidence"] for item in detections], dtype=float)
        class_id = np.array([item["class_id"] for item in detections], dtype=int)
        incoming = sv.Detections(xyxy=xyxy, confidence=confidence, class_id=class_id)
        return _to_dicts(self.tracker.update_with_detections(incoming))


def _to_dicts(tracked: sv.Detections) -> list[dict]:
    if tracked.tracker_id is None or len(tracked) == 0:
        return []
    results = []
    for index, track_id in enumerate(tracked.tracker_id):
        class_id = int(tracked.class_id[index]) if tracked.class_id is not None else 0
        score = float(tracked.confidence[index]) if tracked.confidence is not None else 0.0
        results.append(
            {
                "track_id": str(int(track_id)),
                "bbox_xyxy": [float(v) for v in tracked.xyxy[index].tolist()],
                "class_name": CLASS_NAMES.get(class_id, "object"),
                "class_id": class_id,
                "confidence": score,
            }
        )
    return results
