import cv2
import numpy as np

from app.alignment import ALIGNED, OTHER_VIEW, OUT_OF_VIEW, SHIFTED, UNVERIFIED, VIEW_CHANGED, ViewAligner
from app.drawing import annotate
from app.runtime import place_zone, track_checks

WIDTH, HEIGHT = 960, 540
FLOOR_ZONE = [[0.3, 0.5], [0.6, 0.5], [0.65, 0.8], [0.25, 0.8]]
EDGE_ZONE = [[0.86, 0.4], [0.97, 0.4], [0.97, 0.6], [0.86, 0.6]]


def scene(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    image = np.full((HEIGHT, WIDTH, 3), 128, np.uint8)
    for _ in range(500):
        x, y = int(rng.integers(0, WIDTH)), int(rng.integers(0, HEIGHT))
        w, h = (int(v) for v in rng.integers(8, 50, size=2))
        cv2.rectangle(image, (x, y), (x + w, y + h), tuple(int(c) for c in rng.integers(0, 255, size=3)), -1)
    return image


def moved(image: np.ndarray, dx: float, dy: float, zoom: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    cx, cy = WIDTH / 2, HEIGHT / 2
    matrix = np.array([[zoom, 0, (1 - zoom) * cx + dx], [0, zoom, (1 - zoom) * cy + dy], [0, 0, 1]], dtype=np.float64)
    return cv2.warpPerspective(image, matrix, (WIDTH, HEIGHT)), matrix


def aligner_for(reference: np.ndarray) -> ViewAligner:
    encoded = cv2.imencode(".jpg", reference, [cv2.IMWRITE_JPEG_QUALITY, 90])[1].tobytes()
    return ViewAligner(lambda key: encoded if key == "ref" else None)


def zone(polygon, key="ref", zone_id="z1") -> dict:
    return {"id": zone_id, "name": "Restricted Zone A", "zone_type": "RESTRICTED_AREA", "polygon": polygon, "reference_key": key}


def test_still_camera_keeps_the_zone_as_drawn():
    reference = scene(1)
    view = aligner_for(reference).update(reference, [zone(FLOOR_ZONE)], now=0.0)["z1"]
    assert view.state == ALIGNED
    assert view.polygon == FLOOR_ZONE


def test_small_camera_move_shifts_the_zone_with_the_floor():
    reference = scene(1)
    frame, matrix = moved(reference, dx=35, dy=20, zoom=1.06)
    view = aligner_for(reference).update(frame, [zone(FLOOR_ZONE)], now=0.0)["z1"]
    assert view.state == SHIFTED
    expected = cv2.perspectiveTransform(np.float32([[x * WIDTH, y * HEIGHT] for x, y in FLOOR_ZONE]).reshape(-1, 1, 2), matrix).reshape(-1, 2)
    for (x, y), (ex, ey) in zip(view.polygon, expected):
        assert abs(x * WIDTH - ex) < 3 and abs(y * HEIGHT - ey) < 3


def test_different_view_pauses_after_two_checks_and_resumes_when_it_matches_again():
    reference = scene(1)
    other = scene(2)
    aligner = aligner_for(reference)
    zones = [zone(FLOOR_ZONE)]
    assert aligner.update(reference, zones, now=0.0)["z1"].state == ALIGNED
    assert aligner.update(other, zones, now=1.0)["z1"].state == ALIGNED
    paused = aligner.update(other, zones, now=2.0)["z1"]
    assert paused.state == VIEW_CHANGED and paused.polygon is None
    assert aligner.update(reference, zones, now=3.0)["z1"].state == VIEW_CHANGED
    assert aligner.update(reference, zones, now=4.0)["z1"].state == ALIGNED


def test_zone_pushed_out_of_the_frame_is_paused_while_others_stay_on():
    reference = scene(1)
    frame, _ = moved(reference, dx=140, dy=0)
    views = aligner_for(reference).update(frame, [zone(EDGE_ZONE, zone_id="edge"), zone(FLOOR_ZONE, zone_id="floor")], now=0.0)
    assert views["edge"].state == OUT_OF_VIEW and views["edge"].polygon is None
    assert views["floor"].state == SHIFTED


def test_zone_without_a_reference_is_used_as_drawn():
    reference = scene(1)
    views = aligner_for(reference).update(scene(2), [zone(FLOOR_ZONE, key=None, zone_id="old"), zone(FLOOR_ZONE, key="gone", zone_id="lost")], now=0.0)
    assert views["old"].state == UNVERIFIED and views["old"].polygon == FLOOR_ZONE
    assert views["lost"].state == UNVERIFIED and views["lost"].polygon == FLOOR_ZONE


def test_paused_zone_raises_nothing_and_is_not_drawn():
    reference = scene(1)
    aligner = aligner_for(reference)
    raw = zone(FLOOR_ZONE)
    aligner.update(scene(2), [raw], now=0.0)
    placed = place_zone(raw, aligner.update(scene(2), [raw], now=1.0)["z1"])
    assert placed["view_state"] == VIEW_CHANGED
    rule = {"id": "r1", "zone_id": "z1", "condition_type": "PERSON_INSIDE", "enabled": True}
    assert track_checks([rule], [placed], (0.4, 0.4, 0.5, 0.7), "YES", "CORRECT") == []
    frame = scene(2)
    assert np.array_equal(annotate(frame, [placed], []), frame)


def two_floors() -> tuple[np.ndarray, np.ndarray]:
    """Same shelves on top, different floor paint below, like the two halves of the warehouse clip."""
    shelves = scene(1)
    striped, grid = shelves.copy(), shelves.copy()
    striped[HEIGHT // 2:] = scene(3)[HEIGHT // 2:]
    grid[HEIGHT // 2:] = scene(4)[HEIGHT // 2:]
    return striped, grid


def two_view_aligner(striped: np.ndarray, grid: np.ndarray) -> ViewAligner:
    encoded = {key: cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 90])[1].tobytes() for key, image in (("striped", striped), ("grid", grid))}
    return ViewAligner(encoded.get)


VIEW_ZONES = [zone(FLOOR_ZONE, key="striped", zone_id="lane-1"), zone(FLOOR_ZONE, key="grid", zone_id="lane-2"), zone(EDGE_ZONE, key=None, zone_id="old")]


def test_without_multi_view_both_views_stay_on():
    striped, grid = two_floors()
    views = two_view_aligner(striped, grid).update(grid, VIEW_ZONES, now=0.0)
    assert views["lane-1"].state == ALIGNED and views["lane-2"].state == ALIGNED


def test_multi_view_uses_only_the_best_matching_view():
    striped, grid = two_floors()
    views = two_view_aligner(striped, grid).update(grid, VIEW_ZONES, now=0.0, multi_view=True)
    assert views["lane-2"].state == ALIGNED and views["lane-2"].polygon == FLOOR_ZONE
    assert views["lane-1"].state == OTHER_VIEW and views["lane-1"].polygon is None
    assert views["old"].state == UNVERIFIED and views["old"].polygon == EDGE_ZONE


def test_multi_view_switches_after_two_clear_checks():
    striped, grid = two_floors()
    aligner = two_view_aligner(striped, grid)
    active = lambda views: sorted(key for key in ("lane-1", "lane-2") if views[key].polygon is not None)
    assert active(aligner.update(grid, VIEW_ZONES, now=0.0, multi_view=True)) == ["lane-2"]
    assert active(aligner.update(striped, VIEW_ZONES, now=1.0, multi_view=True)) == ["lane-2"]
    assert active(aligner.update(striped, VIEW_ZONES, now=2.0, multi_view=True)) == ["lane-1"]
    assert active(aligner.update(striped, VIEW_ZONES, now=2.5, multi_view=True)) == ["lane-1"]
