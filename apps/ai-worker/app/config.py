from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", protected_namespaces=())

    api_base_url: str = "http://backend:8000"
    internal_api_token: str = "poc-internal-token"
    ai_mode: str = "DEMO"
    ai_device: str = "cpu"
    model_path: str = "/models"
    default_ai_fps: int = 5
    worker_id: str = "worker-01"
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "safetyadmin"
    minio_secret_key: str = "safetyadmin123"
    minio_bucket: str = "safety-evidence"
    minio_secure: bool = False
    frame_width: int = 960
    frame_height: int = 540


@lru_cache
def get_settings() -> Settings:
    return Settings()
