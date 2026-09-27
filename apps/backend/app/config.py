from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    database_url: str
    redis_url: str = "redis://redis:6379/0"
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "safetyadmin"
    minio_secret_key: str = "safetyadmin123"
    minio_bucket: str = "safety-evidence"
    minio_secure: bool = False
    jwt_secret: str
    jwt_expire_minutes: int = 720
    internal_api_token: str
    ai_mode: str = "DEMO"
    cors_origins: str = "http://localhost:3000"
    demo_admin_password: str = "admin123"
    demo_safety_password: str = "safety123"
    demo_viewer_password: str = "viewer123"
    seed_on_startup: bool = True
    testing: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
