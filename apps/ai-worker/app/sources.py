import logging
from pathlib import Path

import cv2

from app.drawing import synthetic_frame

log = logging.getLogger("worker.source")


class FrameSource:
    def __init__(self, camera_id: str):
        self.camera_id = camera_id
        self.capture = None
        self.kind = None
        self.key = None

    def close(self) -> None:
        if self.capture is not None:
            self.capture.release()
        self.capture = None
        self.kind = None
        self.key = None

    def read(self, camera: dict, store, settings) -> tuple[object | None, str]:
        stream_type = (camera.get("stream_type") or "").upper()
        stream_url = camera.get("stream_url") or ""
        frame = None
        try:
            if stream_type == "RTSP" and stream_url:
                frame = self._read_rtsp(stream_url)
            elif stream_type == "FILE" and stream_url:
                frame = self._read_file(stream_url, store)
        except Exception:
            log.warning("camera source failed", extra={"camera_id": self.camera_id})
            self.close()
            frame = None
        if frame is None:
            if settings.ai_mode.upper() == "DEMO":
                return synthetic_frame(settings.frame_width, settings.frame_height, camera.get("name") or camera.get("code") or "Camera"), "synthetic"
            return None, "offline"
        resized = cv2.resize(frame, (settings.frame_width, settings.frame_height))
        return resized, "video"

    def _read_rtsp(self, url: str):
        if self.kind != "rtsp" or self.key != url or self.capture is None or not self.capture.isOpened():
            self.close()
            self.capture = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
            try:
                self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                pass
            self.kind = "rtsp"
            self.key = url
        if self.capture is None or not self.capture.isOpened():
            self.close()
            return None
        ok, frame = self.capture.read()
        if not ok:
            self.close()
            return None
        return frame

    def _read_file(self, object_key: str, store):
        local = Path("/tmp/safety-videos") / f"{self.camera_id}.mp4"
        if self.kind != "file" or self.key != object_key or self.capture is None or not self.capture.isOpened():
            self.close()
            store.download(object_key, local)
            self.capture = cv2.VideoCapture(str(local))
            self.kind = "file"
            self.key = object_key
            log.info("opened uploaded video", extra={"camera_id": self.camera_id})
        if self.capture is None or not self.capture.isOpened():
            log.warning("uploaded video could not be opened", extra={"camera_id": self.camera_id})
            self.close()
            return None
        ok, frame = self.capture.read()
        if not ok:
            self.capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self.capture.read()
        if not ok:
            self.close()
            return None
        return frame
