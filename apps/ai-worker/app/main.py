import logging
import signal
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.config import get_settings
from app.logging_utils import configure_logging
from app.runtime import CameraLoop

log = logging.getLogger("worker")


class _Ready:
    def __init__(self):
        self.flag = False


READY = _Ready()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/health":
            body = b'{"status":"ok"}'
            self._send(200, body, "application/json")
            return
        if path == "/ready":
            if READY.flag:
                self._send(200, b'{"status":"ready"}', "application/json")
            else:
                self._send(503, b'{"status":"starting"}', "application/json")
            return
        if path == "/metrics":
            self._send(200, generate_latest(), CONTENT_TYPE_LATEST)
            return
        self._send(404, b'{"detail":"not found"}', "application/json")

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return


def serve_http(port: int) -> None:
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()


def main() -> None:
    configure_logging()
    settings = get_settings()
    if settings.ai_mode.upper() not in {"DEMO", "REAL"}:
        raise SystemExit("AI_MODE must be DEMO or REAL")
    # Each camera has its own thread, so OpenCV calls run single-threaded rather than sharing one pool.
    cv2.setNumThreads(1)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    threading.Thread(target=serve_http, args=(8081,), daemon=True).start()
    loops: dict[str, threading.Thread] = {}
    log.info("ai worker started", extra={"camera_id": "-"})
    while not stop.is_set():
        from app.api_client import ApiClient

        client = ApiClient(settings)
        try:
            cameras = client.list_cameras()
            READY.flag = True
        except Exception:
            log.warning("waiting for the backend")
            stop.wait(3)
            continue
        finally:
            client.http.close()
        live_ids = set()
        for camera in cameras:
            assigned = camera.get("assigned_worker")
            if assigned and assigned != settings.worker_id:
                continue
            if not camera.get("enabled"):
                continue
            live_ids.add(camera["id"])
            thread = loops.get(camera["id"])
            if thread is None or not thread.is_alive():
                runner = CameraLoop(camera["id"], settings, stop)

                def _run(loop=runner):
                    try:
                        loop.run()
                    finally:
                        loop.close()

                thread = threading.Thread(target=_run, name=f"cam-{camera['code']}", daemon=True)
                thread.start()
                loops[camera["id"]] = thread
        stop.wait(5)


if __name__ == "__main__":
    main()
