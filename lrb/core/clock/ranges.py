"""Company-local date ranges -> exact UTC instants, for filtering any model."""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone as dt_timezone, tzinfo
from enum import Enum
from typing import Literal, Optional

from django.db.models import QuerySet

from lrb.core.clock.core import local_midnight, local_today, next_day
from lrb.core.exceptions import AppValidationError


class TimePreset(str, Enum):
    TODAY = "TODAY"
    YESTERDAY = "YESTERDAY"
    LAST_7_DAYS = "LAST_7_DAYS"      # today and the 6 days before
    LAST_30_DAYS = "LAST_30_DAYS"    # today and the 29 days before
    THIS_WEEK = "THIS_WEEK"          # Monday..Sunday
    THIS_MONTH = "THIS_MONTH"        # 1st..last day
    LAST_MONTH = "LAST_MONTH"
    THIS_YEAR = "THIS_YEAR"


@dataclass(frozen=True)
class DateRange:
    """Inclusive company-local dates. None on a side means unbounded."""

    start: Optional[date] = None
    end: Optional[date] = None


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def resolve_preset(preset: TimePreset, *, today: date) -> DateRange:
    if preset is TimePreset.TODAY:
        return DateRange(today, today)
    if preset is TimePreset.YESTERDAY:
        y = today - timedelta(days=1)
        return DateRange(y, y)
    if preset is TimePreset.LAST_7_DAYS:
        return DateRange(today - timedelta(days=6), today)
    if preset is TimePreset.LAST_30_DAYS:
        return DateRange(today - timedelta(days=29), today)
    if preset is TimePreset.THIS_WEEK:
        monday = today - timedelta(days=today.weekday())
        return DateRange(monday, monday + timedelta(days=6))
    if preset is TimePreset.THIS_MONTH:
        return DateRange(*_month_bounds(today.year, today.month))
    if preset is TimePreset.LAST_MONTH:
        first_of_this = today.replace(day=1)
        last_prev = first_of_this - timedelta(days=1)
        return DateRange(*_month_bounds(last_prev.year, last_prev.month))
    if preset is TimePreset.THIS_YEAR:
        return DateRange(date(today.year, 1, 1), date(today.year, 12, 31))
    raise AppValidationError(message="Unknown time preset.", field="preset")


def build_date_range(
    *,
    preset: Optional[TimePreset] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    today: Optional[date] = None,
) -> Optional[DateRange]:
    """Validate client input. Returns None when no range was asked for."""
    if preset is not None and (date_from or date_to):
        raise AppValidationError(
            message="Use either a preset or explicit dates, not both.", field="preset"
        )
    if preset is not None:
        return resolve_preset(preset, today=today or local_today())
    if date_from is None and date_to is None:
        return None
    if date_from and date_to and date_from > date_to:
        raise AppValidationError(
            message="The start date must not be after the end date.", field="date_from"
        )
    return DateRange(date_from, date_to)


def to_utc_bounds(
    date_range: DateRange, *, tz: Optional[tzinfo] = None
) -> tuple[Optional[datetime], Optional[datetime]]:
    """(start_inclusive, end_exclusive) as UTC instants.

    The end is the *start of the following local day*, not 'start + 24h', so a
    23- or 25-hour DST day is still covered exactly.
    """
    start = (
        local_midnight(date_range.start, tz=tz).astimezone(dt_timezone.utc)
        if date_range.start
        else None
    )
    end = (
        local_midnight(next_day(date_range.end), tz=tz).astimezone(dt_timezone.utc)
        if date_range.end
        else None
    )
    return start, end


def apply_date_range(
    queryset: QuerySet,
    field: str,
    *,
    date_range: Optional[DateRange],
    kind: Literal["datetime", "date"] = "datetime",
    tz: Optional[tzinfo] = None,
) -> QuerySet:
    """Filter any queryset by company-local dates. Use from every selector.

        qs = apply_date_range(qs, "created_at", date_range=created)
        qs = apply_date_range(qs, "due_on", date_range=due, kind="date")
    """
    if date_range is None:
        return queryset
    if kind == "date":  # DateField: no clock involved, compare calendar days
        if date_range.start:
            queryset = queryset.filter(**{f"{field}__gte": date_range.start})
        if date_range.end:
            queryset = queryset.filter(**{f"{field}__lte": date_range.end})
        return queryset
    start, end = to_utc_bounds(date_range, tz=tz)
    if start:
        queryset = queryset.filter(**{f"{field}__gte": start})
    if end:
        queryset = queryset.filter(**{f"{field}__lt": end})
    return queryset



# Big picture: What does this function do?
# def _month_bounds(year: int, month: int) -> tuple[date, date]:    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])



# The function calculates the first day and last day of a given month.

# For example, imagine you call it with:
# _month_bounds(2026, 2)



# It returns:
# (date(2026, 2, 1), date(2026, 2, 28))



# In other words:
# - First date: February 1, 2026.
# - Last date: February 28, 2026.
# Why would we need this?

# Imagine you're building a system that retrieves all transactions made during February. You need to know when February starts and when it ends. This function calculates those boundaries for you.

# 2. Understanding the function definition
# Let's look at the first line:
# def _month_bounds(year: int, month: int) -> tuple[date, date]:



# There are several things happening here.
# A. def
# def



# This is a Python keyword used to define a function.

# It tells Python:

# "I'm creating a reusable block of code that can perform a particular task."
# B. _month_bounds
# _month_bounds



# This is the function's name.

# The name suggests that it calculates the boundaries (beginning and ending dates) of a month.

# Why does it start with _?

# In Python, a single underscore at the beginning of a function name is a convention indicating that the function is intended for internal use within the module.

# It doesn't make the function private. You can still call it.
# C. year: int
# year: int



# This is a parameter.
# - year is the parameter's name.
# - int is its type hint.
# It tells us that the function expects the year to be an integer.

# Example:
# year = 2026



# D. month: int
# month: int



# This is another parameter.

# It represents the month number:
# Month	Number
# January	1
# February	2
# March	3
# April	4
# December	12

# So:
# _month_bounds(2026, 2)



# passes:
# - 2026 into year.
# - 2 into month.
# E. -> tuple[date, date]
# This is a return type hint.

# Let's break it down:

# ->

# Indicates what type of value the function is expected to return.

# tuple

# A tuple is a Python data structure that can hold multiple values together.

# For example:
# my_tuple = (10, 20)



# date, date

# This tells us that the tuple is expected to contain two date objects.

# So:
# tuple[date, date]



# means:

# "A tuple containing two date values."

# For our function:
# 1. The first date represents the beginning of the month.
# 2. The second date represents the end of the month.

# 3. Understanding the return statement
# Now let's examine the second line:
# return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])



# This is where the actual work happens.

# There are two date() calls.
# A. First date() call
# date(year, month, 1)



# Python's date() constructor creates a date object.

# It accepts three arguments:
# date(year, month, day)



# For example:
# date(2026, 2, 1)



# Creates:
# February 1, 2026


# Notice that the day is explicitly set to 1.

# Why?

# Because the first day of every month is always day 1.

# Therefore:
# date(year, month, 1)



# always gives us the first day of whichever month was supplied.
# B. Second date() call
# This is slightly more complicated:
# date(year, month, calendar.monthrange(year, month)[1])



# Let's start with the innermost part:
# calendar.monthrange(year, month)



# Python has a built-in module called calendar.

# Its monthrange() function returns a tuple containing two values:
# calendar.monthrange(2026, 2)



# Returns:
# (6, 28)



# What do these numbers mean?
# - 6 represents the weekday of the first day of the month (Monday = 0, Sunday = 6).
# - 28 represents the number of days in that month.
# Important: The second value is what we're interested in.
# C. Understanding [1]
# Look at this:
# calendar.monthrange(year, month)[1]



# The [1] means:

# "Get the item at index 1 from the returned tuple."

# Remember, Python indexing starts at zero.

# For example:
# my_tuple = (6, 28)



# Index	Value
# 0	6
# 1	28

# Therefore:
# my_tuple[1]



# returns:
# 28



# So:
# calendar.monthrange(2026, 2)[1]



# returns 28.
# D. Putting everything together
# Now we can understand the second date() call:
# date(year, month, calendar.monthrange(year, month)[1])



# Suppose:
# year = 2026month = 2



# Python evaluates the expression from the inside:

# Step 1:
# calendar.monthrange(2026, 2)



# Result:
# (6, 28)



# Step 2:
# calendar.monthrange(2026, 2)[1]



# Result:
# 28



# Step 3:

# The original expression becomes:
# date(2026, 2, 28)



# Result:
# February 28, 2


# ----------------------------------------------------------------------------
# TIME PRESENTS 
# ----------------------------------------------------------------------------
# Let's Understand resolve_preset
# The big picture
# This function answers one question:

# "The user picked a shortcut like 'Last 7 days' or 'This month'. What actual dates does that mean?"

# You give it:

# A preset (a named choice like TODAY or LAST_7_DAYS)

# Today's date

# It gives you back a DateRange — the real start and end dates that the preset represents.

# Think of it like a translator. The user says "last 7 days" (human words). The function translates that into real dates (machine words).

# The signature
# python
# def resolve_preset(preset: TimePreset, *, today: date) -> DateRange:
# Let's break this down:

# preset: TimePreset → "I need a preset." TimePreset is a fixed list of allowed choices (an enum). Something like: TODAY, YESTERDAY, LAST_7_DAYS, THIS_MONTH, etc.

# *, today: date → "I also need today's date."

# The * is special. It means: "today must be given by name." You must write today=... when calling. You can't just pass it in order.

# Why? Because today is so important, Python wants you to be explicit about it. No accidental mix-ups.

# -> DateRange → "I will give you back a DateRange."

# A subtle but important design choice
# You might wonder: "Why pass today as an argument? Why not just call date.today() inside the function?"

# Because passing it in makes the function testable. In a test, you can say "pretend today is 2026-02-15" and check the result is correct — no matter what day you actually run the test. Very useful.

# Each if block: one preset at a time
# The function is basically a list of cases. Each case says: "If the user picked THIS preset, here is the range."

# Let's go through them one at a time. To make it concrete, I'll pretend:

# Today = Wednesday, November 4, 2026

# Case 1: TODAY
# python
# if preset is TimePreset.TODAY:
#     return DateRange(today, today)
# If the user picks "Today," the start and end are the same day.

# Example: DateRange(Nov 4, Nov 4) → just today.

# Note: DateRange(today, today) works because the fields are start and end in that order. So today → start, today → end.

# Case 2: YESTERDAY
# python
# if preset is TimePreset.YESTERDAY:
#     y = today - timedelta(days=1)
#     return DateRange(y, y)
# timedelta(days=1) means "a length of one day." Subtracting it from a date gives you the day before.

# So today - timedelta(days=1) = yesterday = Nov 3.

# Then we return DateRange(Nov 3, Nov 3) → just yesterday.

# What is timedelta? It's a Python tool from the datetime module that represents a span of time. You can add or subtract it from a date. Like today + timedelta(days=7) = one week from today.

# Case 3: LAST_7_DAYS
# python
# if preset is TimePreset.LAST_7_DAYS:
#     return DateRange(today - timedelta(days=6), today)
# Why 6 and not 7?

# Because "last 7 days" includes today. If you count backward starting at today:

# text
# Day 0 = today       (Nov 4)
# Day 1 = yesterday   (Nov 3)
# Day 2 = Nov 2
# Day 3 = Nov 1
# Day 4 = Oct 31
# Day 5 = Oct 30
# Day 6 = Oct 29  ← 7th day going back
# So the start is today - 6 days = Oct 29, and the end is today = Nov 4.

# That's 7 days total. If they used days=7, you'd get 8 days — off-by-one bug. The 6 is deliberate.

# Result: DateRange(Oct 29, Nov 4)

# Case 4: LAST_30_DAYS
# python
# if preset is TimePreset.LAST_30_DAYS:
#     return DateRange(today - timedelta(days=29), today)
# Same idea as above. 30 days counting backwards from today, so subtract 29 (not 30).

# Result: DateRange(Oct 6, Nov 4) — 30 days total.

# Case 5: THIS_WEEK
# python
# if preset is TimePreset.THIS_WEEK:
#     monday = today - timedelta(days=today.weekday())
#     return DateRange(monday, monday + timedelta(days=6))
# This one needs one new concept: today.weekday().

# It returns a number from 0 to 6 that tells you which day of the week it is:

# Day	weekday()
# Monday	0
# Tuesday	1
# Wednesday	2
# Thursday	3
# Friday	4
# Saturday	5
# Sunday	6
# Monday is 0. So subtracting weekday() days from today takes you back to Monday.

# Example: Today is Wednesday (weekday = 2).

# text
# monday = Nov 4 - 2 days = Nov 2   ← the Monday of this week
# Then the range is from Monday to Monday + 6 days (Sunday):

# text
# DateRange(Nov 2, Nov 8)
# So "this week" means Monday through Sunday.

# Case 6: THIS_MONTH
# python
# if preset is TimePreset.THIS_MONTH:
#     return DateRange(*_month_bounds(today.year, today.month))
# Ah, this is where the earlier function comes back!

# _month_bounds(today.year, today.month) returns two dates: the first and last day of the month.

# For November 2026:

# python
# _month_bounds(2026, 11)   →   (Nov 1, Nov 30)
# But DateRange needs two separate arguments, not a tuple. That's what the * does here.

# What does * mean here?
# The * unpacks the tuple. It's like saying "spread these two values out as separate arguments."

# python
# DateRange(*_month_bounds(2026, 11))
# is the same as:

# python
# DateRange(Nov 1, Nov 30)
# The * says: "Take each item out of the tuple and put it in its own slot."

# Result: DateRange(Nov 1, Nov 30)

# Case 7: LAST_MONTH
# python
# if preset is TimePreset.LAST_MONTH:
#     first_of_this = today.replace(day=1)
#     last_prev = first_of_this - timedelta(days=1)
#     return DateRange(*_month_bounds(last_prev.year, last_prev.month))
# This one is a clever trick. Let's walk through it.

# Goal: get the whole of the previous month.

# Step 1: today.replace(day=1)

# .replace() makes a copy of the date with one part changed. Here we change day to 1. So it becomes the first day of the current month.

# Nov 4 → Nov 1

# Step 2: first_of_this - timedelta(days=1)

# Subtract one day. That gives us the last day of the previous month.

# Nov 1 - 1 day = Oct 31

# Step 3: Now we have a date in October. Use _month_bounds on October's year and month:

# python
# _month_bounds(2026, 10)   →   (Oct 1, Oct 31)
# Then unpack with *:

# python
# DateRange(Oct 1, Oct 31)
# Result: the whole of October.

# Why this trick? Because months don't all have the same number of days, and it's easy to make mistakes with "what month was last month?" (Especially around January.) This method — "go to the 1st of this month, then back off one day" — always lands you safely in the previous month, no matter what.

# Case 8: THIS_YEAR
# python
# if preset is TimePreset.THIS_YEAR:
#     return DateRange(date(today.year, 1, 1), date(today.year, 12, 31))
# Easy. Start = January 1 of this year. End = December 31 of this year.

# Result: DateRange(Jan 1, 2026, Dec 31, 2026)

# The last line: the safety net
# python
# raise AppValidationError(message="Unknown time preset.", field="preset")
# If none of the if conditions matched, this line runs.

# raise means "stop and throw an error." It's a way of saying: "Something went wrong — I don't recognize this preset."

# AppValidationError is a custom error type. It carries:

# message → the human-readable description ("Unknown time preset.")

# field → which field caused the problem ("preset")

# Why is this important?

# Because if someone adds a new preset to TimePreset but forgets to update this function, this line will catch it immediately — instead of silently returning the wrong dates. This is a very good habit.

# Full walkthrough with today = Nov 4, 2026 (Wednesday)
# Preset	Result
# TODAY	Nov 4 → Nov 4
# YESTERDAY	Nov 3 → Nov 3
# LAST_7_DAYS	Oct 29 → Nov 4
# LAST_30_DAYS	Oct 6 → Nov 4
# THIS_WEEK	Nov 2 → Nov 8 (Mon–Sun)
# THIS_MONTH	Nov 1 → Nov 30
# LAST_MONTH	Oct 1 → Oct 31
# THIS_YEAR	Jan 1, 2026 → Dec 31, 2026
# New Python concepts, summarized
# Concept	What it does
# timedelta(days=N)	A length of N days you can add/subtract from a date
# today.weekday()	Returns 0 (Monday) through 6 (Sunday)
# today.replace(day=1)	Returns a copy of the date with one field changed
# *some_tuple	"Unpack" a tuple into separate arguments
# if preset is TimePreset.X	"If the preset is exactly this choice" (is compares identity)
# raise SomeError(...)	Stop and throw an error
# * in the parameter list	Everything after it must be a named argument
# Two subtle things worth noticing
# is instead of ==. For enum members, is is the safe choice — it checks "is this the exact same enum value." It's clearer than == and slightly faster.

# today is passed in, not fetched inside. Every case uses the today argument, never date.today(). This is deliberate — it means the function is pure (given the same inputs, always the same outputs). That makes it easy to test and easy to reason about.

# Would you like me to show you what a test would look like for one of these cases (e.g., how you'd verify LAST_7_DAYS returns the right range when "today" is a specific date)?



# Let's Understand apply_date_range
# The big picture
# This function answers one question:

# "Filter this database query so it only includes rows whose date falls inside the user's chosen range."

# You give it:

# A queryset — a database query that's already in progress (e.g., "all invoices")

# A field name — which date column to filter on (e.g., "created_at" or "due_on")

# A DateRange — the date range the user picked (start/end, either can be None)

# A kind — is that field a datetime (with a clock) or a date (just a day)?

# A timezone — the company's local timezone

# It gives you back a new queryset that's been filtered.

# Think of it like a sieve. You pour all your rows in, and only the ones whose date fits the range come out the other side.

# What's a QuerySet?
# Quick refresher, since it appears in the signature.

# A QuerySet (from Django) is a lazy database query. You build it up step by step:

# python
# Invoice.objects.all()                    # start with everything
#     .filter(status="paid")               # only paid ones
#     .filter(created_at__gte=some_date)   # created after some date
# Each .filter(...) returns a new queryset with an extra condition. Nothing actually hits the database until you iterate or print it — that's why it's called lazy.

# So apply_date_range doesn't fetch anything. It just adds conditions to the query. When the caller finally runs it, the database does the work.

# The signature
# python
# def apply_date_range(
#     queryset: QuerySet,
#     field: str,
#     *,
#     date_range: Optional[DateRange],
#     kind: Literal["datetime", "date"] = "datetime",
#     tz: Optional[tzinfo] = None,
# ) -> QuerySet:
# Let's go through each part:

# Part	Meaning
# queryset: QuerySet	The query to filter (positional)
# field: str	The name of the date column (positional)
# *	Everything after this must be passed by name
# date_range: Optional[DateRange]	The range — or None for "no filter"
# kind: Literal["datetime", "date"] = "datetime"	Only two allowed values: "datetime" or "date" (default "datetime")
# tz: Optional[tzinfo] = None	The company's timezone (default None)
# -> QuerySet	Returns a QuerySet
# New concept: Literal["datetime", "date"]
# This is a type hint that restricts allowed values. It says:

# "This parameter accepts only the string "datetime" or the string "date". Nothing else."

# It's like a dropdown menu with only two options. If you pass "string" or "timestamp", your editor (and tools like mypy) will flag it. It's a safety net.

# Why *?
# Because when you call this function, you want the reader to be explicit:

# python
# apply_date_range(qs, "created_at", date_range=created, kind="datetime", tz=nairobi)
# You can't accidentally swap date_range and kind — they must be named. That's deliberate. It makes the call site self-documenting.

# The docstring examples
# python
# """Filter any queryset by company-local dates. Use from every selector.

#     qs = apply_date_range(qs, "created_at", date_range=created)
#     qs = apply_date_range(qs, "due_on", date_range=due, kind="date")
# """
# This is telling you the intended usage:

# Example 1 — filter invoices by creation time (a datetime field):

# python
# qs = apply_date_range(qs, "created_at", date_range=created)
# Here kind defaults to "datetime", so it treats created_at as a datetime.

# Example 2 — filter invoices by due date (a date field):

# python
# qs = apply_date_range(qs, "due_on", date_range=due, kind="date")
# Here kind="date" is explicit, because due_on is a date (no clock).

# "Use from every selector" — a note to teammates: don't reinvent this. Whenever you need to filter by date, use this function. One place = one behavior = fewer bugs.

# The early exit
# python
# if date_range is None:
#     return queryset
# Translation: "If no date range was given, don't filter at all — return the queryset untouched."

# This is a fast path. If the user didn't pick a date filter, there's nothing to do. Just hand back the original query.

# This is why date_range is Optional. It lets callers say: "no date filter" by passing None.

# Case 1: kind == "date" (DateField)
# python
# if kind == "date":  # DateField: no clock involved, compare calendar days
#     if date_range.start:
#         queryset = queryset.filter(**{f"{field}__gte": date_range.start})
#     if date_range.end:
#         queryset = queryset.filter(**{f"{field}__lte": date_range.end})
#     return queryset
# This branch handles plain dates — no clock, no hours, no minutes. Just calendar days like Feb 1, 2026.

# That comment is key:

# "DateField: no clock involved, compare calendar days"

# So if the user asked for Feb 1 → Feb 28, we want everything where due_on >= Feb 1 and due_on <= Feb 28. Straightforward.

# Let's break the two filters down.

# Filter 1: the start
# python
# queryset.filter(**{f"{field}__gte": date_range.start})
# Three things to understand:

# f"{field}__gte" → builds a string like "due_on__gte". The __gte is Django's lookup syntax meaning "greater than or equal to".

# **{...} → dictionary unpacking. It's like filter(**{"due_on__gte": some_date}), which Django turns into the call filter(due_on__gte=some_date).

# The result → keeps rows where the due_on value is on or after the start date.

# Why the dictionary trick? Because the field name (field) is a variable. You can't write filter(field__gte=...) — that would filter on a literal field called "field". You have to build the key as a string. Dictionary unpacking is the standard Python way to pass dynamic keyword arguments.

# Filter 2: the end
# python
# queryset.filter(**{f"{field}__lte": date_range.end})
# Same idea, but with __lte (less than or equal to).

# due_on__lte = Feb 28 → keeps rows where due_on is on or before Feb 28.

# Notice: __lte on both sides — inclusive on both ends. That matches the DateRange docstring ("Inclusive company-local dates").

# Why is inclusive OK here? Because a DateField has no time component. There's no "Feb 28 23:59:59" — it's just the day Feb 28. So <= is exactly the right comparison.

# But if date_range.start: and if date_range.end:
# Each filter is guarded. If start is None (unbounded on the left), we skip the start filter. If end is None, we skip the end filter.

# This is exactly how DateRange supports open-ended ranges:

# start	end	What happens
# Set	Set	Both filters applied
# None	Set	Only the end filter (everything up to end)
# Set	None	Only the start filter (everything from start onward)
# None	None	Neither filter (no date filtering at all)
# Case 2: kind == "datetime" (DateTimeField)
# python
# start, end = to_utc_bounds(date_range, tz=tz)
# if start:
#     queryset = queryset.filter(**{f"{field}__gte": start})
# if end:
#     queryset = queryset.filter(**{f"{field}__lt": end})
# return queryset
# This branch handles datetime fields — fields that do have a clock. Like created_at, which might be Feb 1, 14:32:07 UTC.

# The tricky part: a datetime has hours, minutes, seconds. So "Feb 1" is not a single point in time — it's a whole 24-hour window. We need to translate the user's "Feb 1" into a start and end that are actual datetimes.

# That's what to_utc_bounds does.

# What is to_utc_bounds?
# It's a helper (defined elsewhere in the codebase). Its job:

# Take the user's local date range (e.g., "Feb 1 to Feb 28, 2026" in Nairobi) and convert it into a UTC half-open range that we can use in a database query.

# Half-open means: include the start, exclude the end. So [start, end).

# Let's say the user picked Feb 1 → Feb 28, 2026, and the company timezone is Nairobi (UTC+3).

# Local start: Feb 1, 00:00:00 Nairobi

# Local end: Feb 28, 23:59:59.999... Nairobi

# Converted to UTC:

# start = Jan 31, 21:00:00 UTC (Feb 1 00:00 Nairobi minus 3 hours)

# end = Feb 28, 21:00:00 UTC (the moment just after the last instant of Feb 28 in Nairobi — i.e., midnight March 1 Nairobi, expressed in UTC)

# So to_utc_bounds returns (start, end) where:

# start = the first instant of the range, in UTC

# end = the first instant after the range, in UTC

# Why "after"? That's the __lt part — see below.

# Filter 1: the start (inclusive)
# python
# queryset.filter(**{f"{field}__gte": start})
# __gte = greater than or equal to. Include rows at or after the start instant.

# Feb 1 00:00:00 Nairobi → converted to UTC → this is start. Include anything at or after that moment. ✅

# Filter 2: the end — notice __lt, not __lte
# python
# queryset.filter(**{f"{field}__lt": end})
# __lt = less than (strictly). Exclude rows at or after end.

# Why strict, not <=? Because end is defined as "the first instant AFTER the range" — i.e., the first moment of the next day in local time. So we want to exclude anything from that moment onward.

# Example with end = Feb 28, 21:00:00 UTC (= midnight March 1 Nairobi):

# A row at Feb 28, 20:59:59 UTC (Feb 28 23:59:59 Nairobi) → included ✅ (it's < end)

# A row at Feb 28, 21:00:00 UTC (March 1 00:00 Nairobi) → excluded ✅ (it's not < end — it's equal)

# That's what "half-open" means: [start, end). It includes the beginning, excludes the very end. Everything from start up to — but not including — end.

# Why is half-open the right choice for datetimes?
# Because two adjacent ranges can share the boundary moment without any row being counted twice, and without any row being missed.

# Suppose you ask for January and then February. With half-open intervals:

# January: [Jan 1, Feb 1)

# February: [Feb 1, Mar 1)

# A row at exactly Feb 1 00:00:00 belongs to February only — not both. Clean.

# With closed intervals [Jan 1, Feb 1] and [Feb 1, Mar 1], that boundary row would be counted twice. Bad.

# With open intervals (Jan 1, Feb 1) and (Feb 1, Mar 1), it would be counted zero times. Also bad.

# Half-open is the sweet spot. It's why to_utc_bounds returns end as "the start of the next day" rather than "the last instant of this day."

# Why can't kind == "date" just do the same thing?
# Because a DateField stores only the calendar day — there's no clock. There's no "midnight boundary" to worry about, because the value Feb 28 is a single point, not a 24-hour window. Feb 28 in Nairobi and Feb 28 in UTC are the same stored value 2026-02-28. There's nothing to convert. So __lte on a DateField is already correct and inclusive — no need for the half-open trick.

# This is the whole reason the kind parameter exists. Datetimes need the UTC conversion and half-open logic; dates don't.

# Side-by-side comparison
# kind="date"	kind="datetime"
# Field type	DateField	DateTimeField
# Has a clock?	No	Yes
# Range per day	Single point	24-hour window
# Need UTC conversion?	No	Yes (via to_utc_bounds)
# Start filter	__gte	__gte
# End filter	__lte (inclusive)	__lt (exclusive)
# Interval style	[start, end] (closed)	[start, end) (half-open)
# Reason	Days are points	Days are windows; half-open avoids double-counting
# Full walkthrough: user picks "February 2026"
# Setup:

# python
# date_range = DateRange(start=date(2026, 2, 1), end=date(2026, 2, 28))
# tz = ZoneInfo("Africa/Nairobi")
# Path A: filter by created_at (datetime)
# python
# qs = apply_date_range(qs, "created_at", date_range=date_range, kind="datetime", tz=tz)
# Step 1: to_utc_bounds(date_range, tz=tz) returns:

# python
# start = datetime(2026, 1, 31, 21, 0, tzinfo=utc)   # Feb 1 00:00 Nairobi
# end   = datetime(2026, 2, 28, 21, 0, tzinfo=utc)   # Mar 1 00:00 Nairobi
# Step 2: Apply:

# python
# qs = qs.filter(created_at__gte=start)   # at or after Jan 31 21:00 UTC
# qs = qs.filter(created_at__lt=end)      # strictly before Feb 28 21:00 UTC
# Result: every row whose created_at falls inside February in Nairobi time — regardless of where in the world the server is.

# Path B: filter by due_on (date)
# python
# qs = apply_date_range(qs, "due_on", date_range=date_range, kind="date")
# Step 1: Skip to_utc_bounds — not needed for plain dates.

# Step 2: Apply:

# python
# qs = qs.filter(due_on__gte=date(2026, 2, 1))   # on or after Feb 1
# qs = qs.filter(due_on__lte=date(2026, 2, 28))  # on or before Feb 28
# Result: every row whose due_on is a calendar day in February.

# Notice the difference: Path A uses <, Path B uses <=. Same intent — different mechanics.

# Why the pattern queryset = queryset.filter(...)?
# You might wonder why not just queryset.filter(...) without reassigning.

# Because querysets are immutable — .filter() returns a new queryset, it doesn't modify the old one. So you must reassign:

# python
# queryset = queryset.filter(...)   # ✅
# If you just wrote queryset.filter(...) and didn't reassign, the new filter would be thrown away. Classic bug.

# Summary table
# Piece	Meaning
# queryset: QuerySet	The query to filter
# field: str	The column to filter on
# *	Everything after must be passed by name
# date_range: Optional[DateRange]	The range — or None for "no filter"
# kind: Literal["datetime", "date"]	Is the field a datetime or a date?
# tz: Optional[tzinfo]	Company timezone (used for datetime conversion)
# if date_range is None: return queryset	Fast path — no filter
# kind == "date"	Compare calendar days; __gte / __lte
# kind == "datetime"	Convert to UTC bounds; __gte / __lt
# to_utc_bounds(...)	Translates local range → UTC half-open range
# **{f"{field}__gte": ...}	Dynamic Django filter via dict unpacking
# __gte	"≥" (greater than or equal)
# __lte	"≤" (less than or equal)
# __lt	"<" (strictly less than)
# Half-open [start, end)	Include start, exclude end — no double counting
# One-line summary
# apply_date_range is a single place that turns a user's date range into a Django filter — correctly, whether the column is a plain date (no timezone math needed) or a datetime (needs UTC conversion and a half-open end). It handles open-ended ranges, an empty range (None), and both field types, so every part of your app filters dates the same way.

# Would you like me to show what to_utc_bounds probably looks like inside — and why it returns end as "the start of the next day" rather than "the last instant of this day"? That's the piece that makes the half-open interval click.

