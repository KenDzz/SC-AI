from app.scenes import scripted_objects
from app.zone_engine import point_in_polygon

RESTRICTED = {
    "zone_type": "RESTRICTED_AREA",
    "polygon": [[0.48, 0.12], [0.92, 0.10], [0.94, 0.62], [0.46, 0.66]],
}
PACKING = {
    "zone_type": "PACKING_ZONE",
    "polygon": [[0.40, 0.20], [0.90, 0.18], [0.92, 0.85], [0.38, 0.88]],
}


def test_walker_starts_outside_and_stands_inside():
    outside = scripted_objects([RESTRICTED], 0.0, False)[0]
    inside = scripted_objects([RESTRICTED], 18.0, False)[0]
    assert point_in_polygon(RESTRICTED["polygon"], outside["nx"], outside["ny"]) is False
    assert point_in_polygon(RESTRICTED["polygon"], inside["nx"], inside["ny"]) is True


def test_hold_inside_places_the_walker_in_the_zone():
    person = scripted_objects([RESTRICTED], 0.0, True)[0]
    assert point_in_polygon(RESTRICTED["polygon"], person["nx"], person["ny"]) is True


def test_packing_scene_has_a_zone_walker_and_an_unknown_person():
    people = [item for item in scripted_objects([PACKING], 18.0, False) if item["class_name"] == "person"]
    assert {item["ppe_mode"] for item in people} == {"zone", "unknown"}
    unknown = next(item for item in people if item["ppe_mode"] == "unknown")
    assert point_in_polygon(PACKING["polygon"], unknown["nx"], unknown["ny"]) is True
