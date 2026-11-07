from __future__ import annotations

from datetime import date, datetime, time, timedelta, tzinfo

from django.utils import timezone as dj_tz


def now() -> datetime:
    """Current instant, timezone-aware, UTC."""
    return dj_tz.now()


def current_timezone() -> tzinfo:
    """Timezone active for this request (the company's, via the middleware)."""
    return dj_tz.get_current_timezone()


def to_local(value: datetime, *, tz: tzinfo | None = None) -> datetime:
    if dj_tz.is_naive(value):
        raise ValueError("Refusing to localize a naive datetime; it has no instant.")
    return value.astimezone(tz or current_timezone())


def local_now(*, tz: tzinfo | None = None) -> datetime:
    return to_local(now(), tz=tz)


def local_today(*, tz: tzinfo | None = None) -> date:
    return local_now(tz=tz).date()


def local_midnight(day: date, *, tz: tzinfo | None = None) -> datetime:
    """Start of `day` on the company's wall clock, as an aware datetime."""
    return datetime.combine(day, time.min, tzinfo=tz or current_timezone())


def next_day(day: date) -> date:
    return day + timedelta(days=1)
