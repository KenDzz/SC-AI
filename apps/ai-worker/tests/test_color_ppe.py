import numpy as np
import pytest

pytest.importorskip("cv2")

from app.detectors import ColorPPEClassifier


def _person(head_bgr: tuple[int, int, int], torso_bgr: tuple[int, int, int]) -> np.ndarray:
    image = np.zeros((140, 70, 3), dtype=np.uint8)
    image[:32] = head_bgr
    image[42:100, 16:54] = torso_bgr
    return image


def test_light_cap_and_workwear_are_compliant():
    result = ColorPPEClassifier().classify(_person((235, 235, 235), (210, 220, 235)))
    assert result["hairnet"] == "YES"
    assert result["uniform"] == "CORRECT"


def test_dark_hair_and_red_shirt_are_violations():
    result = ColorPPEClassifier().classify(_person((25, 25, 25), (30, 30, 210)))
    assert result["hairnet"] == "NO"
    assert result["uniform"] == "INCORRECT"


def test_empty_crop_stays_unknown():
    result = ColorPPEClassifier().classify(np.zeros((0, 0, 3), dtype=np.uint8))
    assert result["hairnet"] == "UNKNOWN"
    assert result["uniform"] == "UNKNOWN"
