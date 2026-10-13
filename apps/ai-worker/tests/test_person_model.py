import numpy as np

from app.detectors import HogPersonDetector, _letterbox


def test_yolox_preprocessing_preserves_bgr_and_top_left_padding():
    image = np.full((100, 200, 3), (10, 80, 230), dtype=np.uint8)
    padded, scale, x, y = _letterbox(image, 416)
    assert scale == 2.08
    assert (x, y) == (0, 0)
    np.testing.assert_array_equal(padded[0, 0], [10, 80, 230])
    np.testing.assert_array_equal(padded[207, 415], [10, 80, 230])
    np.testing.assert_array_equal(padded[208, 0], [114, 114, 114])
    assert padded.dtype == np.float32


def test_hog_detection_does_not_require_visible_skin_or_face():
    # A valid full-body HOG result must survive even on a back-facing crop.
    class StubHog:
        def detectMultiScale(self, image, **kwargs):
            return [(100, 30, 64, 128)], [0.8]

    detector = HogPersonDetector.__new__(HogPersonDetector)
    detector.hog = StubHog()
    image = np.full((360, 640, 3), 40, dtype=np.uint8)
    people = detector.detect(image, [], 0, False)
    assert len(people) == 1
    assert people[0]['bbox_xyxy'] == [100, 30, 164, 158]
