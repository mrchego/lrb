from datetime import date
from typing import List, Optional

import strawberry
from django.utils import timezone

from lrb.accounts.selectors.get_current_user_or_raise import get_current_user_or_raise
from lrb.core.clock.ranges import DateRange, TimePreset, build_date_range
from lrb.core.clock.zones import timezone_choices

strawberry.enum(TimePreset, name="TimePreset")


@strawberry.input
class DateRangeInput:
    """Reusable on any list query: either a preset OR explicit local dates."""

    preset: Optional[TimePreset] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None

    def to_domain(self) -> Optional[DateRange]:
        return build_date_range(
            preset=self.preset, date_from=self.date_from, date_to=self.date_to
        )


@strawberry.type
class ServerTimeType:
    epoch_ms: float
    iso: str


@strawberry.type
class TimeQuery:
    @strawberry.field
    def server_time(self, info: strawberry.Info) -> ServerTimeType:
        get_current_user_or_raise(info)
        moment = timezone.now()
        return ServerTimeType(epoch_ms=moment.timestamp() * 1000, iso=moment.isoformat())

    @strawberry.field
    def timezone_choices(self, info: strawberry.Info) -> List[str]:
        get_current_user_or_raise(info)
        return sorted(timezone_choices())
