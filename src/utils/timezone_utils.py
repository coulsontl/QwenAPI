"""
Timezone utilities for Qwen Code API Server
"""
import os
from datetime import datetime, date, timezone, timedelta
from typing import Optional

from ..config.settings import TZ


def get_local_timezone() -> timezone:
    """获取本地时区"""
    if TZ == "UTC":
        return timezone.utc
    
    # 尝试从环境变量获取时区信息
    try:
        import zoneinfo
        return zoneinfo.ZoneInfo(TZ)
    except (ImportError, OSError):
        # 如果zoneinfo不可用，尝试使用pytz
        try:
            import pytz
            return pytz.timezone(TZ)
        except (ImportError, OSError):
            # 如果都不可用，返回UTC
            return timezone.utc


def get_local_now() -> datetime:
    """获取当前本地时间"""
    local_tz = get_local_timezone()
    return datetime.now(local_tz)


def get_local_today() -> date:
    """获取本地日期"""
    return get_local_now().date()


def get_local_today_iso() -> str:
    """获取本地日期的ISO格式字符串"""
    return get_local_today().isoformat()


def format_local_datetime(dt: datetime) -> str:
    """格式化本地日期时间"""
    if dt.tzinfo is None:
        # 如果是naive datetime，假设是UTC
        dt = dt.replace(tzinfo=timezone.utc)
    
    # 转换为本地时区
    local_tz = get_local_timezone()
    local_dt = dt.astimezone(local_tz)
    
    return local_dt.strftime("%Y-%m-%d %H:%M:%S")


def utc_to_local(utc_dt: datetime) -> datetime:
    """将UTC时间转换为本地时间"""
    if utc_dt.tzinfo is None:
        # 如果是naive datetime，假设是UTC
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    
    local_tz = get_local_timezone()
    return utc_dt.astimezone(local_tz)


def local_to_utc(local_dt: datetime) -> datetime:
    """将本地时间转换为UTC时间"""
    if local_dt.tzinfo is None:
        # 如果是naive datetime，假设是本地时间
        local_tz = get_local_timezone()
        local_dt = local_dt.replace(tzinfo=local_tz)
    
    return local_dt.astimezone(timezone.utc)


def timestamp_to_local_datetime(timestamp: int) -> datetime:
    """将时间戳转换为本地日期时间"""
    utc_dt = datetime.fromtimestamp(timestamp / 1000, timezone.utc)
    return utc_to_local(utc_dt)


def get_timezone_offset_hours() -> float:
    """获取时区偏移小时数"""
    local_tz = get_local_timezone()
    now = datetime.now(local_tz)
    return now.utcoffset().total_seconds() / 3600


def get_timezone_display_name() -> str:
    """获取时区显示名称"""
    offset = get_timezone_offset_hours()
    if offset == 0:
        return "UTC"
    elif offset > 0:
        return f"UTC+{offset}"
    else:
        return f"UTC{offset}"