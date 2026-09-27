import io
import logging

from minio import Minio

from app.config import get_settings

log = logging.getLogger("api.storage")


def client() -> Minio:
    settings = get_settings()
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def ensure_bucket() -> None:
    settings = get_settings()
    store = client()
    if not store.bucket_exists(settings.minio_bucket):
        store.make_bucket(settings.minio_bucket)


def put_bytes(key: str, data: bytes, content_type: str) -> str:
    settings = get_settings()
    client().put_object(settings.minio_bucket, key, io.BytesIO(data), length=len(data), content_type=content_type)
    return key


def get_bytes(key: str) -> bytes | None:
    settings = get_settings()
    try:
        response = client().get_object(settings.minio_bucket, key)
    except Exception:
        log.warning("object read failed for %s", key.split("/")[-1])
        return None
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()
