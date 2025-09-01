"""
Timezone utilities for Qwen Code API Server
"""
import os
from datetime import datetime, date, timezone, timedelta
from typing import Optional

from ..config.settings import TZ


def get_local_timezone() -> timezone:
    if TZ == "UTC":
        return timezone.utc
    
    try:
        import zoneinfo
        return zoneinfo.ZoneInfo(TZ)
    except (ImportError, OSError):
        try:
            import pytz
            return pytz.timezone(TZ)
        except (ImportError, OSError):
            return timezone.utc


def get_local_now() -> datetime:
    local_tz = get_local_timezone()
    return datetime.now(local_tz)


def get_local_today() -> date:
    return get_local_now().date()


def get_local_today_iso() -> str:
    return get_local_today().isoformat()


def format_local_datetime(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    local_tz = get_local_timezone()
    local_dt = dt.astimezone(local_tz)
    
    return local_dt.strftime("%Y-%m-%d %H:%M:%S")


def utc_to_local(utc_dt: datetime) -> datetime:
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    
    local_tz = get_local_timezone()
    return utc_dt.astimezone(local_tz)


def local_to_utc(local_dt: datetime) -> datetime:
    if local_dt.tzinfo is None:
        local_tz = get_local_timezone()
        local_dt = local_dt.replace(tzinfo=local_tz)
    
    return local_dt.astimezone(timezone.utc)


def timestamp_to_local_datetime(timestamp: int) -> datetime:
    utc_dt = datetime.fromtimestamp(timestamp / 1000, timezone.utc)
    return utc_to_local(utc_dt)


def get_timezone_offset_hours() -> float:
    local_tz = get_local_timezone()
    now = datetime.now(local_tz)
    return now.utcoffset().total_seconds() / 3600


def get_timezone_display_name() -> str:
    offset = get_timezone_offset_hours()
    if offset == 0:
        return "UTC"
    elif offset > 0:
        return f"UTC+{offset}"
    else:
        return f"UTC{offset}"