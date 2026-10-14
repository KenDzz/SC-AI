import numpy as np
import pytest

pytest.importorskip("cv2")
import cv2

from app.coffee import (
    BeanTracker,
    BlobCoffeeDetector,
    CoffeeLine,
    CoffeeMonitor,
    DefectAlarm,
    DemoCoffeeDetector,
    build_coffee_detector,
    class_for_stage,
    count_line_y,
    detections_from_rows,
    detections_from_yolo_output,
)
from app.drawing import annotate


BELT = [[0.05, 0.10], [0.95, 0.10], [0.95, 0.90], [0.05, 0.90]]


def _cross(line: CoffeeLine, track: str, klass: str, x: float = 0.4) -> None:
    line.observe([{"track_id": track, "cx": x, "cy": 0.30, "class_name": klass}])
    line.observe([{"track_id": track, "cx": x, "cy": 0.70, "class_name": klass}])


def test_real_mode_without_weights_uses_colour(tmp_path):
    assert isinstance(build_coffee_detector("REAL", str(tmp_path), "cpu"), BlobCoffeeDetector)
    assert isinstance(build_coffee_detector("DEMO", str(tmp_path), "cpu"), DemoCoffeeDetector)


def test_overlay_draws_the_belt_count_and_bean():
    frame = np.zeros((80, 120, 3), dtype=np.uint8)
    zone = {"id": "g", "name": "Green", "zone_type": "GREEN_COFFEE_LINE", "polygon": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]]}
    image = annotate(
        frame,
        [zone],
        [],
        [{"class_name": "black", "bbox_xyxy": [10, 12, 28, 30]}],
        [{"zone_id": "g", "stage": "green", "total": 4, "defect_rate": 0.5}],
    )
    assert not np.array_equal(image, frame)


def test_count_line_sits_halfway_down_the_belt():
    assert count_line_y([[0.1, 0.2], [0.8, 0.2], [0.8, 0.6], [0.1, 0.6]]) == pytest.approx(0.4)


def test_green_bean_is_counted_once_on_the_way_down():
    line = CoffeeLine("green")
    line.set_line(0.5)
    _cross(line, "a", "black")
    line.observe([{"track_id": "a", "cx": 0.4, "cy": 0.8, "class_name": "black"}])
    summary = line.summary(window=10)
    assert summary["total"] == 1
    assert summary["by_class"] == {"black": 1}
    assert summary["defects"] == 1
    assert summary["defect_rate"] == 1.0


def test_a_bean_moving_back_up_the_belt_is_not_counted():
    line = CoffeeLine("green")
    line.set_line(0.5)
    line.observe([{"track_id": "a", "cx": 0.4, "cy": 0.7, "class_name": "good"}])
    line.observe([{"track_id": "a", "cx": 0.4, "cy": 0.3, "class_name": "good"}])
    assert line.summary(window=10)["total"] == 0


def test_roasted_defects_raise_the_rate_and_good_beans_do_not():
    line = CoffeeLine("roasted")
    line.set_line(0.5)
    _cross(line, "q", "quaker", 0.2)
    _cross(line, "g", "good", 0.5)
    _cross(line, "m", "mould", 0.7)
    summary = line.summary(window=10)
    assert summary["total"] == 3
    assert summary["defects"] == 2
    assert summary["defect_rate"] == pytest.approx(2 / 3)
    assert set(summary["by_class"]) == {"quaker", "good", "mould"}


def test_count_stage_records_quantity_without_a_defect_rate():
    line = CoffeeLine("count")
    line.set_line(0.5)
    line.observe([{"track_id": "b", "cx": 0.2, "cy": 0.3, "class_name": "black"}])
    line.observe([{"track_id": "b", "cx": 0.2, "cy": 0.7, "class_name": "black"}])
    summary = line.summary(window=10)
    assert summary["total"] == 1
    assert summary["defects"] == 0
    assert summary["defect_rate"] == 0.0
    assert summary["by_class"] == {"bean": 1}


def test_quality_window_forgets_beans_that_left_it():
    line = CoffeeLine("green")
    line.set_line(0.5)
    _cross(line, "1", "good", 0.2)
    _cross(line, "2", "good", 0.4)
    _cross(line, "3", "black", 0.6)
    summary = line.summary(window=2)
    assert summary["total"] == 3
    assert summary["window_total"] == 2
    assert summary["defects"] == 1
    assert summary["defect_rate"] == 0.5


def test_class_ids_follow_the_belt_stage():
    assert class_for_stage("green", 1) == "black"
    assert class_for_stage("green", 4) == "sour"
    assert class_for_stage("green", 5) is None
    assert class_for_stage("roasted", 0) == "good"
    assert class_for_stage("roasted", 5) == "quaker"
    assert class_for_stage("roasted", 8) == "mould"
    assert class_for_stage("roasted", 2) is None
    assert class_for_stage("count", 6) == "bean"
    assert class_for_stage("count", 99) is None


def test_onnx_rows_keep_only_the_classes_for_that_stage():
    rows = np.array(
        [
            [10, 20, 40, 50, 0.9, 1],
            [10, 20, 40, 50, 0.2, 1],
            [60, 20, 90, 50, 0.8, 5],
        ],
        dtype=float,
    )
    found = detections_from_rows(rows, "green", frame_w=100, frame_h=100, input_w=100, input_h=100)
    assert [item["class_name"] for item in found] == ["black"]
    assert found[0]["cx"] == pytest.approx(0.25)
    assert found[0]["cy"] == pytest.approx(0.35)


def test_yolo_head_uses_the_nine_class_ids_and_suppresses_duplicates():
    head = np.zeros((1, 13, 2), dtype=np.float32)
    head[0, 0, :] = 16
    head[0, 1, :] = 8
    head[0, 2, :] = 8
    head[0, 3, :] = 8
    head[0, 5, 0] = 0.91
    head[0, 5, 1] = 0.62
    green = detections_from_yolo_output(head, "green", frame_w=32, frame_h=32, input_w=32, input_h=32)
    assert [item["class_name"] for item in green] == ["black"]
    assert green[0]["cx"] == pytest.approx(0.5)
    assert green[0]["cy"] == pytest.approx(0.25)
    assert detections_from_yolo_output(head, "roasted", frame_w=32, frame_h=32, input_w=32, input_h=32) == []
    counted = detections_from_yolo_output(head, "count", frame_w=32, frame_h=32, input_w=32, input_h=32)
    assert [item["class_name"] for item in counted] == ["bean"]


def test_tracker_keeps_one_id_while_a_bean_moves_a_short_way():
    tracker = BeanTracker()
    first = tracker.update([{"cx": 0.20, "cy": 0.20, "class_name": "good", "confidence": 0.9, "bbox_xyxy": [1, 2, 3, 4]}])
    second = tracker.update([{"cx": 0.22, "cy": 0.28, "class_name": "good", "confidence": 0.9, "bbox_xyxy": [1, 2, 3, 4]}])
    assert first[0]["track_id"] == second[0]["track_id"]


def test_defect_alarm_opens_after_the_rate_holds_and_closes_when_it_falls():
    alarm = DefectAlarm()
    assert alarm.update(True, 0.0, min_duration_s=2.0, cooldown_s=10.0, grace_s=1.0) is None
    opened = alarm.update(True, 2.0, min_duration_s=2.0, cooldown_s=10.0, grace_s=1.0)
    assert opened is not None and opened.kind == "open"
    assert alarm.update(True, 2.5, min_duration_s=2.0, cooldown_s=10.0, grace_s=1.0) is None
    assert alarm.update(False, 3.0, min_duration_s=2.0, cooldown_s=10.0, grace_s=1.0) is None
    alarm.attach("inc-1")
    closed = alarm.update(False, 4.2, min_duration_s=2.0, cooldown_s=10.0, grace_s=1.0)
    assert closed is not None and closed.kind == "close" and closed.incident_id == "inc-1"
    assert alarm.update(True, 6.0, min_duration_s=2.0, cooldown_s=10.0, grace_s=1.0) is None
    assert alarm.update(True, 16.0, min_duration_s=2.0, cooldown_s=10.0, grace_s=1.0) is None
    reopened = alarm.update(True, 18.0, min_duration_s=2.0, cooldown_s=10.0, grace_s=1.0)
    assert reopened is not None and reopened.kind == "open"


def _paint(stage_color: tuple[int, int, int], shape: str = "oval", hole: bool = False) -> tuple[np.ndarray, list]:
    image = np.full((180, 280, 3), (180, 180, 180), dtype=np.uint8)
    if shape == "flat":
        cv2.ellipse(image, (140, 90), (70, 14), 0, 0, 360, stage_color, -1)
    else:
        cv2.ellipse(image, (140, 90), (28, 18), 0, 0, 360, stage_color, -1)
    if hole:
        cv2.circle(image, (140, 90), 5, (8, 8, 8), -1)
    return image, [[0.05, 0.05], [0.95, 0.05], [0.95, 0.95], [0.05, 0.95]]


def test_blob_detector_names_green_defects():
    detector = BlobCoffeeDetector()
    expected = {
        (50, 140, 70): "good",
        (16, 16, 16): "black",
        (210, 215, 205): "fade",
        (30, 210, 230): "sour",
    }
    for color, name in expected.items():
        frame, polygon = _paint(color)
        found = detector.detect_in_polygon(frame, polygon, "green")
        assert [item["class_name"] for item in found] == [name]
    frame, polygon = _paint((50, 140, 70), shape="flat")
    found = detector.detect_in_polygon(frame, polygon, "green")
    assert [item["class_name"] for item in found] == ["broken"]


def test_dark_factory_belt_still_finds_separate_beans():
    detector = BlobCoffeeDetector()
    image = np.full((180, 280, 3), (35, 48, 32), dtype=np.uint8)
    cv2.ellipse(image, (70, 90), (16, 11), 0, 0, 360, (40, 80, 140), -1)
    cv2.ellipse(image, (150, 90), (16, 11), 0, 0, 360, (190, 210, 220), -1)
    cv2.ellipse(image, (220, 90), (16, 11), 0, 0, 360, (12, 12, 12), -1)
    found = detector.detect_in_polygon(image, [[0.05, 0.05], [0.95, 0.05], [0.95, 0.95], [0.05, 0.95]], "count")
    assert len(found) == 3
    assert {item["class_name"] for item in found} == {"bean"}


def test_blob_detector_names_roasted_defects_and_count_ignores_colour():
    detector = BlobCoffeeDetector()
    roasted = {
        (45, 80, 130): "good",
        (170, 200, 220): "quaker",
        (12, 12, 12): "burnt",
        (40, 150, 60): "mould",
    }
    for color, name in roasted.items():
        frame, polygon = _paint(color)
        found = detector.detect_in_polygon(frame, polygon, "roasted")
        assert [item["class_name"] for item in found] == [name], color
    frame, polygon = _paint((45, 80, 130), hole=True)
    found = detector.detect_in_polygon(frame, polygon, "roasted")
    assert [item["class_name"] for item in found] == ["insect"]
    frame, polygon = _paint((16, 16, 16))
    found = detector.detect_in_polygon(frame, polygon, "count")
    assert [item["class_name"] for item in found] == ["bean"]


def test_demo_lines_count_green_and_roasted_defects_and_count_only_quantity():
    green = {"id": "g", "name": "Green belt", "zone_type": "GREEN_COFFEE_LINE", "polygon": [[0.05, 0.04], [0.95, 0.04], [0.95, 0.30], [0.05, 0.30]]}
    roasted = {"id": "r", "name": "Roast belt", "zone_type": "ROASTED_COFFEE_LINE", "polygon": [[0.05, 0.36], [0.95, 0.36], [0.95, 0.62], [0.05, 0.62]]}
    counted = {"id": "c", "name": "Count belt", "zone_type": "COFFEE_COUNT_LINE", "polygon": [[0.05, 0.68], [0.95, 0.68], [0.95, 0.96], [0.05, 0.96]]}
    zones = [green, roasted, counted]
    rules = [
        {
            "id": "rg",
            "zone_id": "g",
            "enabled": True,
            "condition_type": "DEFECT_RATE",
            "event_type": "GREEN_COFFEE_DEFECT_RATE",
            "severity": "HIGH",
            "min_duration_ms": 500,
            "cooldown_ms": 5000,
            "grace_ms": 200,
            "extensions": {"max_defect_rate": 0.2, "window": 4},
        },
        {
            "id": "rr",
            "zone_id": "r",
            "enabled": True,
            "condition_type": "DEFECT_RATE",
            "event_type": "ROASTED_COFFEE_DEFECT_RATE",
            "severity": "HIGH",
            "min_duration_ms": 500,
            "cooldown_ms": 5000,
            "grace_ms": 200,
            "extensions": {"max_defect_rate": 0.2, "window": 4},
        },
    ]
    detector = DemoCoffeeDetector()
    monitor = CoffeeMonitor()
    frame = np.zeros((540, 960, 3), dtype=np.uint8)
    opened = []
    reports = []
    for step in range(48):
        now = step * 0.25
        raw = detector.detect(frame, zones, now, False)
        _, reports, actions = monitor.step(raw, zones, rules, now)
        opened.extend(action.event_type for action in actions if action.kind == "open")
    by_id = {item["zone_id"]: item for item in reports}
    assert by_id["g"]["total"] >= 4
    assert by_id["g"]["defect_rate"] > 0.2
    assert set(by_id["g"]["by_class"]) <= {"good", "black", "broken", "fade", "sour"}
    assert "black" in by_id["g"]["by_class"] or by_id["g"]["defects"] > 0
    assert by_id["r"]["total"] >= 4
    assert by_id["r"]["defect_rate"] > 0.2
    assert set(by_id["r"]["by_class"]) <= {"good", "quaker", "burnt", "insect", "mould"}
    assert by_id["c"]["total"] >= 4
    assert by_id["c"]["defect_rate"] == 0.0
    assert set(by_id["c"]["by_class"]) == {"bean"}
    assert "GREEN_COFFEE_DEFECT_RATE" in opened
    assert "ROASTED_COFFEE_DEFECT_RATE" in opened


def test_camera_loop_inspects_green_roasted_and_count_belts():
    import threading

    from app.config import Settings
    from app.runtime import CameraLoop

    green = {"id": "g", "name": "Green belt", "zone_type": "GREEN_COFFEE_LINE", "polygon": [[0.05, 0.04], [0.95, 0.04], [0.95, 0.30], [0.05, 0.30]]}
    roasted = {"id": "r", "name": "Roast belt", "zone_type": "ROASTED_COFFEE_LINE", "polygon": [[0.05, 0.36], [0.95, 0.36], [0.95, 0.62], [0.05, 0.62]]}
    counted = {"id": "c", "name": "Count belt", "zone_type": "COFFEE_COUNT_LINE", "polygon": [[0.05, 0.68], [0.95, 0.68], [0.95, 0.96], [0.05, 0.96]]}
    rules = [
        {
            "id": "rg",
            "zone_id": "g",
            "enabled": True,
            "condition_type": "DEFECT_RATE",
            "event_type": "GREEN_COFFEE_DEFECT_RATE",
            "severity": "HIGH",
            "min_duration_ms": 500,
            "cooldown_ms": 5000,
            "grace_ms": 200,
            "extensions": {"max_defect_rate": 0.15, "window": 8},
        }
    ]
    loop = CameraLoop("cam-bean", Settings(ai_mode="DEMO", config_refresh_s=60, heartbeat_every_s=60), threading.Event())
    frame = np.zeros((540, 960, 3), dtype=np.uint8)
    reports = []
    opened = []
    for step in range(48):
        _, reports, actions = loop._inspect_coffee({"zones": [green, roasted, counted], "rules": rules}, frame, step * 0.25, False)
        opened.extend(action.event_type for action in actions if action.kind == "open")
    by_id = {item["zone_id"]: item for item in reports}
    assert by_id["g"]["total"] >= 8
    assert by_id["g"]["defect_rate"] > 0.15
    assert by_id["r"]["stage"] == "roasted" and by_id["r"]["total"] >= 4
    assert by_id["c"]["stage"] == "count" and by_id["c"]["defect_rate"] == 0.0 and by_id["c"]["total"] >= 4
    assert opened == ["GREEN_COFFEE_DEFECT_RATE"]
