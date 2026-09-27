from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

FACTORY_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def today_bounds(now: datetime | None = None) -> tuple[datetime, datetime]:
    current = now.astimezone(FACTORY_TZ) if now else datetime.now(FACTORY_TZ)
    start = current.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def day_bounds(day_text: str) -> tuple[datetime, datetime]:
    year, month, day = [int(part) for part in day_text.split("-")]
    start = datetime(year, month, day, tzinfo=FACTORY_TZ)
    return start, start + timedelta(days=1)
