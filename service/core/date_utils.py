"""Calendar-day bounds in the project's local wall-clock time (MySQL DATETIME)."""
from datetime import date, datetime, timedelta
from fastapi import HTTPException


def parse_day(value: str) -> date:
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError()
        return parsed
    except (TypeError, ValueError):
        raise HTTPException(422, detail="日期必须为有效的YYYY-MM-DD")


def end_exclusive(value: str | None):
    if not value:
        return None
    return datetime.combine(parse_day(value) + timedelta(days=1), datetime.min.time())


def date_bounds(start: str | None, end: str | None):
    first = datetime.combine(parse_day(start), datetime.min.time()) if start else None
    last = end_exclusive(end)
    if first and last and first >= last:
        raise HTTPException(422, detail="起始日期不能晚于结束日期")
    return first, last


def shanghai_today():
    # Shanghai has no daylight-saving transitions in the supported modern ranges.
    from datetime import timezone
    return datetime.now(timezone(timedelta(hours=8))).date()
