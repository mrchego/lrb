"""Pure unit tests: no database, no tenants."""
from datetime import date, datetime, timezone as dt_utc
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone as dj_tz

from lrb.core.clock import (
    DateRange, TimePreset, build_date_range, local_today, resolve_preset, to_utc_bounds,
)
from lrb.core.clock.zones import timezone_choices
from lrb.core.exceptions import AppValidationError
from lrb.core.validators.date_format import validate_date_format
from lrb.core.validators.timezone_name import validate_timezone_name

NAIROBI = ZoneInfo("Africa/Nairobi")  # UTC+3, no DST
NEW_YORK = ZoneInfo("America/New_York")


def test_nairobi_day_is_21h_utc_to_21h_utc():
    start, end = to_utc_bounds(DateRange(date(2026, 11, 5), date(2026, 11, 5)), tz=NAIROBI)
    assert start == datetime(2026, 11, 4, 21, 0, tzinfo=dt_utc.utc)
    assert end == datetime(2026, 11, 5, 21, 0, tzinfo=dt_utc.utc)


def test_end_date_is_inclusive_and_end_bound_exclusive():
    start, end = to_utc_bounds(DateRange(date(2026, 11, 5), date(2026, 11, 6)), tz=NAIROBI)
    assert (end - start).total_seconds() == 48 * 3600


def test_dst_spring_forward_day_is_23_hours():
    start, end = to_utc_bounds(DateRange(date(2026, 3, 8), date(2026, 3, 8)), tz=NEW_YORK)
    assert (end - start).total_seconds() == 23 * 3600


def test_dst_fall_back_day_is_25_hours():
    start, end = to_utc_bounds(DateRange(date(2026, 11, 1), date(2026, 11, 1)), tz=NEW_YORK)
    assert (end - start).total_seconds() == 25 * 3600


def test_late_night_nairobi_is_still_today_not_tomorrow_utc():
    # 23:30 in Nairobi on the 5th is 20:30 UTC on the 5th; 00:30 Nairobi on the 6th is 21:30 UTC on the 5th.
    with dj_tz.override(NAIROBI):
        instant = datetime(2026, 11, 5, 21, 30, tzinfo=dt_utc.utc)
        assert instant.astimezone(NAIROBI).date() == date(2026, 11, 6)


def test_local_today_follows_the_given_zone(monkeypatch):
    fixed = datetime(2026, 11, 5, 22, 0, tzinfo=dt_utc.utc)
    monkeypatch.setattr("lrb.core.clock.core.now", lambda: fixed)
    assert local_today(tz=dt_utc.utc) == date(2026, 11, 5)
    assert local_today(tz=NAIROBI) == date(2026, 11, 6)


@pytest.mark.parametrize(
    "preset,expected",
    [
        (TimePreset.TODAY, (date(2026, 11, 5), date(2026, 11, 5))),
        (TimePreset.YESTERDAY, (date(2026, 11, 4), date(2026, 11, 4))),
        (TimePreset.LAST_7_DAYS, (date(2026, 10, 30), date(2026, 11, 5))),
        (TimePreset.LAST_30_DAYS, (date(2026, 10, 7), date(2026, 11, 5))),
        (TimePreset.THIS_WEEK, (date(2026, 11, 2), date(2026, 11, 8))),  # Thu -> Mon..Sun
        (TimePreset.THIS_MONTH, (date(2026, 11, 1), date(2026, 11, 30))),
        (TimePreset.LAST_MONTH, (date(2026, 10, 1), date(2026, 10, 31))),
        (TimePreset.THIS_YEAR, (date(2026, 1, 1), date(2026, 12, 31))),
    ],
)
def test_presets(preset, expected):
    r = resolve_preset(preset, today=date(2026, 11, 5))
    assert (r.start, r.end) == expected


def test_last_month_across_year_boundary():
    r = resolve_preset(TimePreset.LAST_MONTH, today=date(2027, 1, 15))
    assert (r.start, r.end) == (date(2026, 12, 1), date(2026, 12, 31))


def test_build_rejects_preset_plus_dates():
    with pytest.raises(AppValidationError):
        build_date_range(preset=TimePreset.TODAY, date_from=date(2026, 1, 1))


def test_build_rejects_reversed_range():
    with pytest.raises(AppValidationError):
        build_date_range(date_from=date(2026, 2, 1), date_to=date(2026, 1, 1))


def test_build_returns_none_when_nothing_given():
    assert build_date_range() is None


def test_open_ended_range():
    start, end = to_utc_bounds(DateRange(date(2026, 11, 5), None), tz=NAIROBI)
    assert start is not None and end is None


@pytest.mark.parametrize("bad", ["", "Mars/Base", "../etc/passwd", "EST5EDT", "Etc/GMT+5", "US/Eastern", "nairobi"])
def test_timezone_validator_rejects(bad):
    with pytest.raises(AppValidationError):
        validate_timezone_name(value=bad)


@pytest.mark.parametrize("good", ["UTC", "Africa/Nairobi", "Europe/London", "America/New_York"])
def test_timezone_validator_accepts(good):
    assert validate_timezone_name(value=good) == good


def test_choices_contain_only_loadable_zones():
    for name in timezone_choices():
        ZoneInfo(name)


def test_date_format_validator():
    assert validate_date_format(value="DD/MM/YYYY") == "DD/MM/YYYY"
    with pytest.raises(AppValidationError):
        validate_date_format(value="YY-M-D")
