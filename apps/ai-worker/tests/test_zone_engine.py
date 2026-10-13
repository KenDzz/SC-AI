from app.zone_engine import bbox_center_in_polygon, bbox_foot_in_polygon, point_in_polygon

SQUARE = [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]]
FORKLIFT_LANE = [[0.08, 0.58], [0.88, 0.56], [0.90, 0.96], [0.06, 0.98]]
RESTRICTED = [[0.48, 0.12], [0.92, 0.10], [0.94, 0.62], [0.46, 0.66]]


def test_point_inside():
    assert point_in_polygon(SQUARE, 0.5, 0.5) is True


def test_point_outside():
    assert point_in_polygon(SQUARE, 0.1, 0.1) is False


def test_point_on_boundary_is_inside():
    assert point_in_polygon(SQUARE, 0.2, 0.5) is True


def test_bbox_center_inside_and_outside():
    assert bbox_center_in_polygon(SQUARE, (0.4, 0.4, 0.6, 0.6)) is True
    assert bbox_center_in_polygon(SQUARE, (0.0, 0.0, 0.1, 0.1)) is False


def test_bbox_foot_uses_bottom_centre():
    assert bbox_foot_in_polygon(SQUARE, (0.4, 0.0, 0.6, 0.5)) is True
    assert bbox_foot_in_polygon(SQUARE, (0.4, 0.5, 0.6, 0.9)) is False


def test_person_standing_in_forklift_lane_is_not_placed_in_the_zone_behind():
    # Warehouse frame: the worker's feet are on the lane, the box centre projects onto the restricted area.
    box = (0.367, 0.169, 0.576, 0.913)
    assert bbox_center_in_polygon(RESTRICTED, box) is True
    assert bbox_foot_in_polygon(RESTRICTED, box) is False
    assert bbox_foot_in_polygon(FORKLIFT_LANE, box) is True


def test_degenerate_polygon():
    assert point_in_polygon([[0.1, 0.1], [0.2, 0.2]], 0.1, 0.1) is False
    assert point_in_polygon([], 0.5, 0.5) is False
