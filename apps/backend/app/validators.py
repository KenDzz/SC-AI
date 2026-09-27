ZONE_TYPES = {
    "RESTRICTED_AREA",
    "MACHINE_DANGER_ZONE",
    "FORKLIFT_LANE",
    "PRODUCTION_ZONE",
    "PACKING_ZONE",
}
EVENT_TYPES = {
    "RESTRICTED_AREA_INTRUSION",
    "HAIRNET_VIOLATION",
    "UNIFORM_VIOLATION",
    "MACHINE_DANGER_ZONE_INTRUSION",
    "PEDESTRIAN_IN_FORKLIFT_ZONE",
}
CONDITION_TYPES = {"PERSON_INSIDE", "HAIRNET_MISSING", "UNIFORM_INCORRECT"}
SEVERITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
STREAM_TYPES = {"RTSP", "FILE"}
STATUSES = {"NEW", "CONFIRMED", "FALSE_POSITIVE", "RESOLVED"}
REVIEW_TRANSITIONS = {
    "NEW": {"CONFIRMED", "FALSE_POSITIVE", "RESOLVED"},
    "CONFIRMED": {"FALSE_POSITIVE", "RESOLVED"},
    "FALSE_POSITIVE": set(),
    "RESOLVED": set(),
}


def validate_polygon(points: list[list[float]]) -> list[list[float]]:
    if len(points) < 3:
        raise ValueError("A zone needs at least 3 points")
    cleaned = []
    for point in points:
        if len(point) != 2:
            raise ValueError("Each point needs an x and y value")
        x, y = float(point[0]), float(point[1])
        if not 0 <= x <= 1 or not 0 <= y <= 1:
            raise ValueError("Zone points must be between 0 and 1")
        cleaned.append([round(x, 5), round(y, 5)])
    return cleaned
