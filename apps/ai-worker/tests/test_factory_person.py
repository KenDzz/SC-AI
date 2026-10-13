import numpy as np
import pytest

pytest.importorskip("cv2")

from app.detectors import FactoryPersonDetector


def test_white_hairnet_above_a_face_is_a_person():
    frame = np.full((240, 320, 3), (70, 80, 90), dtype=np.uint8)
    frame[40:58, 150:172] = (230, 230, 230)
    frame[58:88, 152:170] = (90, 140, 190)
    # The legacy head heuristic requires facial texture, not a flat swatch.
    frame[58:88:2, 152:170] = (120, 170, 220)
    frame[88:170, 140:185] = (170, 200, 220)
    people = FactoryPersonDetector().detect(frame, [], 0, False)
    assert people
    box = people[0]["bbox_xyxy"]
    assert box[0] < 160 < box[2]
    assert box[1] <= 40 < box[3]


def test_plain_machine_rectangle_is_not_a_person():
    frame = np.full((240, 320, 3), (80, 80, 80), dtype=np.uint8)
    frame[20:150, 30:120] = (140, 145, 150)
    frame[40:130, 50:70] = (90, 90, 95)
    people = FactoryPersonDetector().detect(frame, [], 0, False)
    assert people == []
