from app.zone_engine import bbox_center_in_polygon, point_in_polygon

SQUARE = [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]]


def test_point_inside():
    assert point_in_polygon(SQUARE, 0.5, 0.5) is True


def test_point_outside():
    assert point_in_polygon(SQUARE, 0.1, 0.1) is False


def test_point_on_boundary_is_inside():
    assert point_in_polygon(SQUARE, 0.2, 0.5) is True


def test_bbox_center_inside_and_outside():
    assert bbox_center_in_polygon(SQUARE, (0.4, 0.4, 0.6, 0.6)) is True
    assert bbox_center_in_polygon(SQUARE, (0.0, 0.0, 0.1, 0.1)) is False


def test_degenerate_polygon():
    assert point_in_polygon([[0.1, 0.1], [0.2, 0.2]], 0.1, 0.1) is False
    assert point_in_polygon([], 0.5, 0.5) is False
