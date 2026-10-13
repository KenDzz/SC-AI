from app.drawing import CHECK_COLORS, NO_RULE_COLOR, track_color
from app.runtime import track_checks

RESTRICTED = {
    "id": "zone-restricted",
    "name": "Restricted Zone A",
    "zone_type": "RESTRICTED_AREA",
    "polygon": [[0.48, 0.12], [0.92, 0.10], [0.94, 0.62], [0.46, 0.66]],
}
PACKING = {
    "id": "zone-packing",
    "name": "Packing Zone A",
    "zone_type": "PACKING_ZONE",
    "polygon": [[0.0, 0.0], [0.4, 0.0], [0.4, 1.0], [0.0, 1.0]],
}
ZONES = [RESTRICTED, PACKING]

FEET_IN_RESTRICTED = (0.6, 0.2, 0.7, 0.5)
FEET_IN_PACKING = (0.1, 0.2, 0.2, 0.8)
FEET_IN_NO_ZONE = (0.6, 0.6, 0.7, 0.9)


def rule(zone: dict, condition: str, enabled: bool = True) -> dict:
    return {"id": f"{zone['id']}-{condition}", "zone_id": zone["id"], "condition_type": condition, "enabled": enabled}


def test_person_in_restricted_zone_is_a_violation_even_with_correct_ppe():
    checks = track_checks([rule(RESTRICTED, "PERSON_INSIDE")], ZONES, FEET_IN_RESTRICTED, "YES", "CORRECT")
    assert checks == [{"text": "In Restricted Zone A", "state": "violation"}]
    assert track_color({"class_name": "person", "checks": checks}) == CHECK_COLORS["violation"]


def test_ppe_is_reported_only_where_a_ppe_rule_applies():
    rules = [rule(RESTRICTED, "PERSON_INSIDE"), rule(PACKING, "HAIRNET_MISSING")]
    assert track_checks(rules, ZONES, FEET_IN_PACKING, "NO", "CORRECT") == [{"text": "Hairnet: No", "state": "violation"}]
    assert track_checks(rules, ZONES, FEET_IN_PACKING, "YES", "CORRECT") == [{"text": "Hairnet: Yes", "state": "ok"}]
    assert track_checks(rules, ZONES, FEET_IN_PACKING, "UNKNOWN", "CORRECT") == [{"text": "Hairnet: Unknown", "state": "unknown"}]
    assert track_checks(rules, ZONES, FEET_IN_NO_ZONE, "NO", "INCORRECT") == []


def test_disabled_rules_are_ignored():
    assert track_checks([rule(RESTRICTED, "PERSON_INSIDE", enabled=False)], ZONES, FEET_IN_RESTRICTED, "YES", "CORRECT") == []


def test_box_colour_follows_the_worst_check():
    ok = {"text": "Hairnet: Yes", "state": "ok"}
    unknown = {"text": "Uniform: Unknown", "state": "unknown"}
    violation = {"text": "In Restricted Zone A", "state": "violation"}
    assert track_color({"class_name": "person", "checks": [ok, violation]}) == CHECK_COLORS["violation"]
    assert track_color({"class_name": "person", "checks": [ok, unknown]}) == CHECK_COLORS["unknown"]
    assert track_color({"class_name": "person", "checks": [ok]}) == CHECK_COLORS["ok"]
    assert track_color({"class_name": "person", "checks": []}) == NO_RULE_COLOR
