from fastapi.testclient import TestClient

from app.main import app
from app.mask import mask_stream_url
from app.validators import validate_polygon


def client():
    return TestClient(app)


def auth(api: TestClient, username: str, password: str) -> dict:
    response = api.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_health_and_seed_login():
    with client() as api:
        assert api.get("/health").json()["status"] == "ok"
        assert api.get("/ready").status_code == 200
        headers = auth(api, "admin", "admin123")
        cameras = api.get("/api/cameras", headers=headers)
        assert cameras.status_code == 200
        codes = {item["code"] for item in cameras.json()}
        assert codes == {"CAM-PACK-01", "CAM-PROD-01", "CAM-MACHINE-01", "CAM-WAREHOUSE-01"}
        rules = api.get("/api/rules", headers=headers).json()
        assert {item["event_type"] for item in rules} == {
            "HAIRNET_VIOLATION",
            "UNIFORM_VIOLATION",
            "MACHINE_DANGER_ZONE_INTRUSION",
            "RESTRICTED_AREA_INTRUSION",
            "PEDESTRIAN_IN_FORKLIFT_ZONE",
        }
        assert api.get("/api/incidents", headers=headers).json()["total"] >= 9


def test_viewer_cannot_configure_and_safety_can_review():
    with client() as api:
        viewer = auth(api, "viewer", "viewer123")
        denied = api.post(
            "/api/cameras",
            headers=viewer,
            json={"code": "CAM-X", "name": "Extra", "area": "Packing Area", "stream_type": "FILE"},
        )
        assert denied.status_code == 403
        safety = auth(api, "safety", "safety123")
        incidents = api.get("/api/incidents?status=NEW", headers=safety).json()["items"]
        assert incidents
        updated = api.post(f"/api/incidents/{incidents[0]['id']}/confirm", headers=safety, json={"comment": "Checked on the floor"})
        assert updated.status_code == 200
        assert updated.json()["status"] == "CONFIRMED"
        again = api.post(f"/api/incidents/{incidents[0]['id']}/confirm", headers=safety, json={"comment": "again"})
        assert again.status_code == 409


def test_worker_token_and_masking():
    with client() as api:
        denied = api.get("/api/internal/cameras", headers={"X-Internal-Token": "nope"})
        assert denied.status_code == 401
        allowed = api.get("/api/internal/cameras", headers={"X-Internal-Token": "test-internal"})
        assert allowed.status_code == 200
        assert len(allowed.json()) == 4
    assert mask_stream_url("rtsp://operator:s3cret@10.0.0.5/live") == "rtsp://operator:***@10.0.0.5/live"
    assert "s3cret" not in mask_stream_url("rtsp://operator:s3cret@10.0.0.5/live")


def test_camera_ai_fps_saves_25_and_rejects_31():
    with client() as api:
        headers = auth(api, "admin", "admin123")
        camera = api.get("/api/cameras", headers=headers).json()[0]
        assert camera["ai_fps"] == 25
        lowered = api.patch(f"/api/cameras/{camera['id']}", headers=headers, json={"ai_fps": 8})
        assert lowered.status_code == 200, lowered.text
        assert lowered.json()["ai_fps"] == 8
        raised = api.patch(f"/api/cameras/{camera['id']}", headers=headers, json={"ai_fps": 25})
        assert raised.status_code == 200, raised.text
        assert raised.json()["ai_fps"] == 25
        rejected = api.patch(f"/api/cameras/{camera['id']}", headers=headers, json={"ai_fps": 31})
        assert rejected.status_code == 422


def test_polygon_must_be_normalized():
    try:
        validate_polygon([[0.1, 0.1], [1.2, 0.2], [0.2, 0.8]])
    except ValueError as exc:
        assert "between 0 and 1" in str(exc)
    else:
        raise AssertionError("expected a validation error")


def test_polygon_takes_any_number_of_corners_but_no_crossing_edges():
    l_shape = [[0.1, 0.1], [0.6, 0.1], [0.6, 0.4], [0.3, 0.4], [0.3, 0.9], [0.1, 0.9]]
    assert validate_polygon(l_shape) == l_shape
    assert len(validate_polygon(l_shape[:3] + [[0.45, 0.4]] + l_shape[3:])) == 7
    assert validate_polygon([[0.1, 0.1], [0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.1]]) == [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5]]
    for points, message in (
        ([[0.1, 0.1], [0.9, 0.9], [0.9, 0.1], [0.1, 0.9]], "cross"),
        ([[0.1, 0.1], [0.5, 0.5], [0.9, 0.9]], "no area"),
        ([[0.2, 0.2], [0.2, 0.2], [0.2, 0.2]], "3 different points"),
    ):
        try:
            validate_polygon(points)
        except ValueError as exc:
            assert message in str(exc)
        else:
            raise AssertionError(f"expected a validation error for {points}")


def test_admin_redraws_a_zone_in_place_and_its_rules_stay():
    with client() as api:
        headers = auth(api, "admin", "admin123")
        rule = next(item for item in api.get("/api/rules", headers=headers).json() if item["event_type"] == "RESTRICTED_AREA_INTRUSION")
        shape = [[0.5, 0.4], [0.7, 0.38], [0.8, 0.5], [0.72, 0.62], [0.55, 0.6], [0.48, 0.5]]
        redrawn = api.patch(f"/api/zones/{rule['zone_id']}", headers=headers, json={"polygon": shape})
        assert redrawn.status_code == 200, redrawn.text
        assert redrawn.json()["id"] == rule["zone_id"]
        assert redrawn.json()["polygon"] == shape
        assert redrawn.json()["name"] == rule["zone_name"]
        still = next(item for item in api.get("/api/rules", headers=headers).json() if item["id"] == rule["id"])
        assert still["zone_id"] == rule["zone_id"]
        crossing = api.patch(f"/api/zones/{rule['zone_id']}", headers=headers, json={"polygon": [[0.1, 0.1], [0.9, 0.9], [0.9, 0.1], [0.1, 0.9]]})
        assert crossing.status_code == 400
        assert "cross" in crossing.json()["detail"]
        viewer = auth(api, "viewer", "viewer123")
        assert api.patch(f"/api/zones/{rule['zone_id']}", headers=viewer, json={"polygon": shape}).status_code == 403


def test_zone_keeps_the_frame_it_was_drawn_on(monkeypatch):
    from app.routers import catalog

    objects: dict[str, bytes] = {}
    monkeypatch.setattr(catalog, "get_bytes", lambda key: objects.get(key))
    monkeypatch.setattr(catalog, "put_bytes", lambda key, data, content_type: objects.__setitem__(key, data))
    with client() as api:
        headers = auth(api, "admin", "admin123")
        camera = next(item for item in api.get("/api/cameras", headers=headers).json() if item["code"] == "CAM-WAREHOUSE-01")
        frames = f"/api/cameras/{camera['id']}/reference-frames"
        assert api.post(frames, headers=headers).status_code == 404
        objects[f"cameras/{camera['id']}/latest_raw.jpg"] = b"frame drawn on"
        frozen = api.post(frames, headers=headers).json()["id"]
        objects[f"cameras/{camera['id']}/latest_raw.jpg"] = b"a later frame"
        assert api.get(f"{frames}/{frozen}", headers=headers).content == b"frame drawn on"

        shape = [[0.1, 0.6], [0.4, 0.6], [0.4, 0.9], [0.1, 0.9]]
        zone = api.post("/api/zones", headers=headers, json={"camera_id": camera["id"], "name": "Dock", "zone_type": "RESTRICTED_AREA", "polygon": shape, "reference_id": frozen}).json()
        key = f"cameras/{camera['id']}/references/{frozen}.jpg"
        assert zone["reference_key"] == key
        worker = api.get("/api/internal/cameras", headers={"X-Internal-Token": "test-internal"}).json()
        assert next(item for cam in worker for item in cam["zones"] if item["id"] == zone["id"])["reference_key"] == key

        url = f"/api/zones/{zone['id']}"
        assert api.patch(url, headers=headers, json={"name": "Dock A"}).json()["reference_key"] == key
        assert api.patch(url, headers=headers, json={"polygon": shape}).json()["reference_key"] is None
        assert api.patch(url, headers=headers, json={"reference_id": frozen}).json()["reference_key"] == key
        assert api.patch(url, headers=headers, json={"reference_id": "../latest_raw"}).status_code == 400
        assert api.patch(url, headers=headers, json={"reference_id": "0" * 32}).status_code == 400
        api.delete(url, headers=headers)


def test_multi_view_is_off_by_default_and_reaches_the_worker():
    with client() as api:
        headers = auth(api, "admin", "admin123")
        camera = next(item for item in api.get("/api/cameras", headers=headers).json() if item["code"] == "CAM-WAREHOUSE-01")
        assert camera["multi_view"] is False
        updated = api.patch(f"/api/cameras/{camera['id']}", headers=headers, json={"multi_view": True})
        assert updated.status_code == 200 and updated.json()["multi_view"] is True
        worker = api.get("/api/internal/cameras", headers={"X-Internal-Token": "test-internal"}).json()
        assert next(item for item in worker if item["id"] == camera["id"])["multi_view"] is True
        api.patch(f"/api/cameras/{camera['id']}", headers=headers, json={"multi_view": False})
