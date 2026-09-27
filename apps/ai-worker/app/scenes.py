"""Scripted DEMO paths. People walk into the configured polygons so every rule can be shown."""

from app.zone_engine import point_in_polygon, representative_point

PERIOD_S = 36.0


def _lerp(a: tuple[float, float], b: tuple[float, float], t: float) -> tuple[float, float]:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def _outside(polygon: list[list[float]], anchor: tuple[float, float]) -> tuple[float, float]:
    candidates = [
        (max(0.02, min(0.98, anchor[0] - 0.4)), anchor[1]),
        (0.03, anchor[1]),
        (0.03, 0.06),
        (0.97, 0.06),
    ]
    for point in candidates:
        if not point_in_polygon(polygon, point[0], point[1]):
            return point
    return (0.03, 0.06)


def _inside_corner(polygon: list[list[float]], anchor: tuple[float, float]) -> tuple[float, float]:
    xs = [point[0] for point in polygon]
    ys = [point[1] for point in polygon]
    corner = (min(xs) + 0.05, min(ys) + 0.05)
    if point_in_polygon(polygon, corner[0], corner[1]):
        return corner
    return anchor


def walk(now: float, polygon: list[list[float]], anchor: tuple[float, float], hold_inside: bool, phase: float) -> tuple[float, float]:
    if hold_inside:
        return anchor
    outside = _outside(polygon, anchor)
    progress = ((now + phase) % PERIOD_S) / PERIOD_S
    if progress < 0.4:
        return _lerp(outside, anchor, progress / 0.4)
    if progress < 0.7:
        return anchor
    return _lerp(anchor, outside, (progress - 0.7) / 0.3)


def scripted_objects(zones: list[dict], now: float, hold_inside: bool) -> list[dict]:
    objects: list[dict] = []
    for index, zone in enumerate(zones):
        polygon = zone.get("polygon") or []
        anchor = representative_point(polygon)
        if anchor is None:
            continue
        zone_type = zone.get("zone_type")
        position = walk(now, polygon, anchor, hold_inside, phase=index * 3.0)
        objects.append({"class_name": "person", "ppe_mode": "zone", "nx": position[0], "ny": position[1]})
        if zone_type in {"PACKING_ZONE", "PRODUCTION_ZONE"}:
            corner = _inside_corner(polygon, anchor)
            objects.append({"class_name": "person", "ppe_mode": "unknown", "nx": corner[0], "ny": corner[1]})
        if zone_type == "FORKLIFT_LANE":
            parked = (min(0.96, anchor[0] + 0.16), anchor[1])
            if not point_in_polygon(polygon, parked[0], parked[1]):
                parked = anchor
            objects.append({"class_name": "forklift", "ppe_mode": "none", "nx": parked[0], "ny": parked[1]})
    return objects
