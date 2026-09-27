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
