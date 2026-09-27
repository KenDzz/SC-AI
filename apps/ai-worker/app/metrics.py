from prometheus_client import Counter, Gauge, Histogram

frames_processed = Counter("safety_frames_processed_total", "Frames processed by the AI worker", ["camera_id"])
dropped_frames = Counter("safety_dropped_frames_total", "Frames skipped because processing ran behind the camera FPS", ["camera_id"])
detections_total = Counter("safety_detections_total", "Objects returned by the detector", ["camera_id"])
incidents_created = Counter("safety_incidents_created_total", "Incidents accepted by the API", ["camera_id"])
inference_latency = Histogram(
    "safety_inference_latency_seconds",
    "Time spent in detection, tracking, and PPE classification",
    ["camera_id"],
)
camera_fps = Gauge("safety_camera_ai_fps", "Recently achieved AI frames per second", ["camera_id"])
camera_up = Gauge("safety_camera_up", "1 when a camera loop is processing frames", ["camera_id"])
