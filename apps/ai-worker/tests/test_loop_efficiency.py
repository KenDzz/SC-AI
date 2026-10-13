import threading
from pathlib import Path

import pytest

from app.config import Settings
from app.detectors import build_detectors
from app.runtime import CameraLoop

CAMERA = {
    "id": "cam-1",
    "factory_id": "f-1",
    "code": "CAM-1",
    "name": "Camera 1",
    "stream_type": "FILE",
    "stream_url": "",
    "enabled": True,
    "ai_fps": 5,
    "assigned_worker": None,
    "simulate_pending": False,
    "zones": [],
    "rules": [],
}


class FakeApi:
    def __init__(self, cameras: list[dict]):
        self.cameras = cameras
        self.config_calls = 0
        self.heartbeats: list[str] = []
        self.acks = 0

    def list_cameras(self) -> list[dict]:
        self.config_calls += 1
        return self.cameras

    def heartbeat(self, camera_id: str, payload: dict) -> None:
        self.heartbeats.append(payload["status"])

    def ack_simulate(self, camera_id: str) -> None:
        self.acks += 1


def loop_with(cameras: list[dict]) -> tuple[CameraLoop, FakeApi]:
    settings = Settings(ai_mode="DEMO", config_refresh_s=60, heartbeat_every_s=60)
    loop = CameraLoop("cam-1", settings, threading.Event())
    fake = FakeApi(cameras)
    loop.api = fake
    loop.store.put_bytes = lambda *args, **kwargs: None
    return loop, fake


def test_camera_config_is_fetched_once_per_refresh_period():
    loop, api = loop_with([CAMERA])
    for _ in range(5):
        assert loop._camera()["id"] == "cam-1"
    assert api.config_calls == 1
    loop.config_at = float("-inf")
    loop._camera()
    assert api.config_calls == 2


def test_heartbeats_are_throttled_but_a_status_change_goes_out_at_once():
    loop, api = loop_with([CAMERA])
    for _ in range(5):
        loop._heartbeat(CAMERA, "AI_PROCESSING", [], 0, 0)
    loop._heartbeat(CAMERA, "OFFLINE", [], 0, 0)
    assert api.heartbeats == ["AI_PROCESSING", "OFFLINE"]


def test_simulate_is_acknowledged_once_while_the_config_is_cached():
    loop, api = loop_with([{**CAMERA, "simulate_pending": True}])
    for _ in range(3):
        loop._step(loop._camera())
    assert api.acks == 1


@pytest.mark.skipif(not (Path("/models") / "person.onnx").exists(), reason="person.onnx is not installed")
def test_onnx_sessions_use_a_few_threads_that_do_not_spin():
    detector, *_ = build_detectors("REAL", "/models", "cpu", threads=2)
    options = detector.session.get_session_options()
    assert options.intra_op_num_threads == 2
    assert options.get_session_config_entry("session.intra_op.allow_spinning") == "0"
