import io
from pathlib import Path

from minio import Minio

from app.config import Settings


class ObjectStore:
    def __init__(self, settings: Settings):
        self.bucket = settings.minio_bucket
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )

    def put_bytes(self, key: str, data: bytes, content_type: str) -> None:
        self.client.put_object(self.bucket, key, io.BytesIO(data), length=len(data), content_type=content_type)

    def download(self, key: str, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.client.fget_object(self.bucket, key, str(path))
