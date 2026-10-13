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
    """Any number of corners, in order around the area. Edges must not cross."""
    if len(points) < 3:
        raise ValueError("A zone needs at least 3 points")
    cleaned: list[list[float]] = []
    for point in points:
        if len(point) != 2:
            raise ValueError("Each point needs an x and y value")
        x, y = float(point[0]), float(point[1])
        if not 0 <= x <= 1 or not 0 <= y <= 1:
            raise ValueError("Zone points must be between 0 and 1")
        rounded = [round(x, 5), round(y, 5)]
        if not cleaned or cleaned[-1] != rounded:
            cleaned.append(rounded)
    if len(cleaned) > 1 and cleaned[0] == cleaned[-1]:
        cleaned.pop()
    if len(cleaned) < 3:
        raise ValueError("A zone needs at least 3 different points")
    if _edges_cross(cleaned):
        raise ValueError("Zone edges cross each other. Click the corners in order around the area")
    if _area(cleaned) < 1e-4:
        raise ValueError("The zone has no area. Its points lie on one line")
    return cleaned


def _area(points: list[list[float]]) -> float:
    total = 0.0
    for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1]):
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def _edges_cross(points: list[list[float]]) -> bool:
    """True when two edges that do not share a corner touch or cross.

    The worker repairs such a shape by dropping part of it, so the saved zone
    would silently cover less than what was drawn.
    """
    edges = list(zip(points, points[1:] + points[:1]))
    count = len(edges)
    for i in range(count):
        for j in range(i + 2, count):
            if i == 0 and j == count - 1:
                continue
            if _segments_touch(*edges[i], *edges[j]):
                return True
    return False


def _segments_touch(p1, p2, q1, q2) -> bool:
    o1, o2 = _orientation(p1, p2, q1), _orientation(p1, p2, q2)
    o3, o4 = _orientation(q1, q2, p1), _orientation(q1, q2, p2)
    if o1 != o2 and o3 != o4:
        return True
    return (
        (o1 == 0 and _within(p1, p2, q1))
        or (o2 == 0 and _within(p1, p2, q2))
        or (o3 == 0 and _within(q1, q2, p1))
        or (o4 == 0 and _within(q1, q2, p2))
    )


def _orientation(a, b, c) -> int:
    value = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    if abs(value) < 1e-12:
        return 0
    return 1 if value > 0 else -1


def _within(a, b, c) -> bool:
    return min(a[0], b[0]) <= c[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= c[1] <= max(a[1], b[1])
