import redis

from app.config import get_settings

_client: redis.Redis | None = None


def get_redis() -> redis.Redis | None:
    global _client
    if _client is not None:
        return _client
    try:
        client = redis.Redis.from_url(get_settings().redis_url, decode_responses=True)
        client.ping()
        _client = client
        return client
    except Exception:
        return None


def publish(channel: str, message: str) -> None:
    client = get_redis()
    if client is None:
        return
    try:
        client.publish(channel, message)
    except Exception:
        return
