"""Normalized polygon checks. Coordinates are fractions of the frame, from 0 to 1."""

from shapely.geometry import Point, Polygon


def as_polygon(points: list[list[float]] | None) -> Polygon | None:
    if not points or len(points) < 3:
        return None
    try:
        polygon = Polygon([(float(x), float(y)) for x, y in points])
    except (TypeError, ValueError):
        return None
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    if polygon.is_empty or not isinstance(polygon, Polygon):
        return None
    return polygon


def point_in_polygon(points: list[list[float]] | None, x: float, y: float) -> bool:
    polygon = as_polygon(points)
    if polygon is None:
        return False
    return bool(polygon.covers(Point(float(x), float(y))))


def bbox_center_in_polygon(points: list[list[float]] | None, bbox: tuple[float, float, float, float]) -> bool:
    x1, y1, x2, y2 = bbox
    return point_in_polygon(points, (float(x1) + float(x2)) / 2.0, (float(y1) + float(y2)) / 2.0)


def representative_point(points: list[list[float]] | None) -> tuple[float, float] | None:
    polygon = as_polygon(points)
    if polygon is None:
        return None
    point = polygon.representative_point()
    return float(point.x), float(point.y)


def bbox_overlap_ratio(points: list[list[float]] | None, bbox: tuple[float, float, float, float]) -> float:
    """Reserved for a later overlap rule. Returns the fraction of the bbox inside the zone."""
    polygon = as_polygon(points)
    if polygon is None:
        return 0.0
    x1, y1, x2, y2 = bbox
    box = Polygon([(x1, y1), (x2, y1), (x2, y2), (x1, y2)])
    if not box.is_valid or box.area <= 0:
        return 0.0
    return float(polygon.intersection(box).area / box.area)
