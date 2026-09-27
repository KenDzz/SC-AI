import logging

import httpx

from app.config import Settings

log = logging.getLogger("worker.api")


class ApiClient:
    def __init__(self, settings: Settings):
        self.base = settings.api_base_url.rstrip("/")
        self.http = httpx.Client(
            timeout=30.0,
            headers={"X-Internal-Token": settings.internal_api_token},
        )

    def list_cameras(self) -> list[dict]:
        response = self.http.get(f"{self.base}/api/internal/cameras")
        response.raise_for_status()
        return response.json()

    def heartbeat(self, camera_id: str, payload: dict) -> None:
        response = self.http.post(f"{self.base}/api/internal/cameras/{camera_id}/heartbeat", json=payload)
        response.raise_for_status()

    def ack_simulate(self, camera_id: str) -> None:
        response = self.http.post(f"{self.base}/api/internal/cameras/{camera_id}/simulate-ack")
        response.raise_for_status()

    def open_incident(self, payload: dict) -> dict:
        response = self.http.post(f"{self.base}/api/internal/incidents", json=payload)
        response.raise_for_status()
        return response.json()

    def close_incident(self, incident_id: str, ended_at: str) -> None:
        response = self.http.post(
            f"{self.base}/api/internal/incidents/{incident_id}/close",
            json={"ended_at": ended_at},
        )
        response.raise_for_status()
