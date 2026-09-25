from datetime import timedelta
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from lrb.accounts.models import User
from lrb.staff.models import Invitation
from django.db.models import Q


def get_user_stats(*, company_id: str):
    qs = User.objects.filter(company_id=company_id)
    stats = qs.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        locked=Count("id", filter=Q(locked_until__gt=timezone.now())),
    )
    pending_invitations = Invitation.objects.filter(
        company_id=company_id, used=False
    ).count()
    since = timezone.now() - timedelta(days=30)
    daily = (
        qs.filter(created_at__gte=since)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )

    return {
        **stats,
        "pending_invitations": pending_invitations,
        "signups_last_30_days": [
            {"date": d["day"].isoformat(), "value": d["count"]} for d in daily
        ],
    }


# Yes. This is a very good piece of Django code to learn from because it combines imports, functions, Django QuerySets, filtering, aggregation, dates, dictionaries, list comprehensions, and ** dictionary unpacking.

# I’ll explain it from the ground up, especially the parts that can look confusing.

# 1. First: what is this function trying to do?

# The whole function:

# def get_user_stats(*, company_id: str):

# is basically a statistics collector.

# Imagine your database contains users:

# Company A
# ├── John      active
# ├── Mary      active
# ├── Peter     locked
# └── James     active

# Company B
# ├── David     active
# └── Sarah     active

# You want statistics only for Company A.

# The function will eventually return something like:

# {
#     "total": 4,
#     "active": 3,
#     "locked": 1,
#     "pending_invitations": 2,
#     "signups_last_30_days": [
#         {"date": "2026-08-28", "value": 1},
#         {"date": "2026-09-02", "value": 2},
#         {"date": "2026-09-10", "value": 1},
#     ],
# }

# So conceptually:

# get_user_stats()
#        │
#        ├── How many users?
#        ├── How many active?
#        ├── How many locked?
#        ├── How many pending invitations?
#        └── How many users signed up each day during last 30 days?

# That's the big picture.

# 2. Before reading the code: understand the imports

# Let's go one by one.

# from datetime import timedelta
# from datetime import timedelta

# Python has a module called:

# datetime

# Inside that module is something called:

# timedelta

# timedelta represents a duration of time.

# For example:

# timedelta(days=30)

# means:

# a duration of 30 days.

# You can think of it as:

# 30 days

# rather than an actual date.

# Later we'll see:

# timezone.now() - timedelta(days=30)

# which means:

# "Give me the date/time from 30 days ago."

# 3. Django Count
# from django.db.models import Count

# Count is used to count database records.

# For example:

# Count("id")

# basically means:

# "Count the IDs."

# If the database contains:

# id
# ---
# 1
# 2
# 3
# 4
# 5

# then:

# Count("id")

# produces:

# 5

# You'll see this later:

# total=Count("id")

# which means:

# Create a statistic called total containing the number of users.

# 4. TruncDate
# from django.db.models.functions import TruncDate

# This one is more interesting.

# Imagine created_at contains:

# 2026-09-20 14:32:51

# That's a datetime:

# date + time

# But maybe your statistics don't care about the exact time.

# You want:

# 2026-09-20

# TruncDate means approximately:

# "Take the datetime and reduce it down to just the date."

# So:

# TruncDate("created_at")

# turns something conceptually like:

# 2026-09-20 14:32:51

# into:

# 2026-09-20

# This will become important when creating the daily signup statistics.

# 5. Django timezone
# from django.utils import timezone

# This gives you Django's timezone-aware date/time functions.

# The important one here is:

# timezone.now()

# which means:

# "Give me the current date and time."

# For example:

# 2026-09-24 11:20:00
# 6. Importing your User model
# from lrb.accounts.models import User

# This is your application's User model.

# So when you see:

# User.objects

# you're working with the database records represented by your User model.

# Think:

# User model
#      ↓
# database table containing users
# 7. Importing Invitation
# from lrb.staff.models import Invitation

# This is another model.

# Probably something conceptually like:

# Invitation
# -----------------
# id
# company_id
# email
# used
# created_at
# ...

# So later:

# Invitation.objects

# means:

# "Work with invitation records in the database."

# 8. Importing Q
# from django.db.models import Q

# Q is used to build conditions for database queries.

# For example:

# Q(is_active=True)

# means:

# "is_active must be True."

# Another example:

# Q(age__gte=18)

# means:

# "age is greater than or equal to 18."

# In your code, Q is used here:

# filter=Q(is_active=True)

# We'll get there.

# 9. Now the function
# def get_user_stats(*, company_id: str):

# Let's break this apart.

# def
# def

# means:

# "I'm defining a function."

# Function name
# get_user_stats

# This is the name of the function.

# The name tells us:

# "Get user statistics."

# company_id
# company_id

# This is an argument the function needs.

# Someone might call:

# get_user_stats(company_id="abc123")

# The function then knows:

# "I need statistics for company abc123."

# : str
# company_id: str

# This is a type hint.

# It tells the reader:

# company_id is expected to be a string.

# It doesn't itself convert the value to a string.

# It's information for humans, editors, type checkers, etc.

# 10. What does the * mean?

# This is worth learning carefully.

# You have:

# def get_user_stats(*, company_id: str):

# The * means:

# company_id must be passed using its name.

# So this is allowed:

# get_user_stats(company_id="123")

# But this is not the intended calling style:

# get_user_stats("123")

# Why do that?

# Because it makes the function call clearer.

# Compare:

# get_user_stats("123")

# with:

# get_user_stats(company_id="123")

# The second one immediately tells you:

# "123 is the company ID."

# 11. First real line
# qs = User.objects.filter(company_id=company_id)

# This is one of the most important lines.

# Let's read it from left to right.

# User
# User

# Your Django User model.

# .objects
# User.objects

# Django gives models a manager called objects.

# You can think of it as:

# "The thing I use to ask the database for User records."

# .filter(...)
# User.objects.filter(...)

# means:

# "Give me User records matching these conditions."

# company_id=company_id

# This can initially look confusing because the same name appears twice.

# company_id=company_id

# The left side:

# company_id

# is the database/model field.

# The right side:

# company_id

# is the function argument.

# So:

# User.objects.filter(company_id=company_id)

# means:

# "Find Users whose database company_id equals the company_id passed into this function."

# For example, if:

# company_id = "abc"

# then conceptually:

# User.objects.filter(company_id="abc")
# 12. What is qs?
# qs = User.objects.filter(company_id=company_id)

# qs commonly means:

# QuerySet

# A QuerySet represents a collection of database records that you're asking Django for.

# So mentally:

# qs
#  ↓
# Users belonging to this company

# For example:

# qs
#  ↓
# John
# Mary
# Peter
# James

# An important Django concept:

# A QuerySet is not simply a Python list.

# It's Django's database-query representation.

# Django can continue building the query:

# qs.filter(...)
# qs.annotate(...)
# qs.values(...)
# qs.order_by(...)

# That's exactly what this code does later.

# 13. Now:
# stats = qs.aggregate(

# We're creating another variable:

# stats

# This will eventually contain something like:

# {
#     "total": 4,
#     "active": 3,
#     "locked": 1,
# }

# The important word is:

# aggregate

# Aggregation means:

# Take many database rows and calculate summary information from them.

# For example:

# Users
# -----
# John
# Mary
# Peter
# James

# Instead of returning all four users, aggregation gives you:

# total = 4
# 14. First statistic
# total=Count("id"),

# Read it as:

# total
#   =
# Count("id")

# The name:

# total

# will become the dictionary key.

# The calculation:

# Count("id")

# counts user IDs.

# So if there are 100 users:

# total=Count("id")

# produces:

# "total": 100
# 15. The interesting part: active
# active=Count("id", filter=Q(is_active=True)),

# This is more complicated.

# Let's break it down:

# Count(
#     "id",
#     filter=Q(is_active=True)
# )

# There are two important pieces:

# "id"

# and:

# filter=Q(is_active=True)
# "id"
# Count("id")

# means:

# Count user IDs.

# Q(is_active=True)

# This creates a database condition:

# is_active=True

# Meaning:

# Only consider users whose is_active field is True.

# So:

# Count("id", filter=Q(is_active=True))

# means:

# Count user IDs, but only for users where is_active=True.

# 16. Example

# Suppose the company has:

# John    is_active=True
# Mary    is_active=True
# Peter   is_active=False
# James   is_active=True
# Sarah   is_active=False

# Total:

# 5

# Active:

# 3

# So:

# stats

# becomes:

# {
#     "total": 5,
#     "active": 3,
# }
# 17. Now the locked calculation
# locked=Count(
#     "id",
#     filter=Q(locked_until__gt=timezone.now())
# ),

# This looks complicated, but it follows the same pattern.

# First:

# Count("id")

# Count IDs.

# Then:

# filter=...

# But only count records satisfying this condition.

# The condition is:

# Q(locked_until__gt=timezone.now())
# 18. What does __gt mean?

# This is a very important Django lookup syntax.

# locked_until__gt

# The double underscore:

# __

# is used by Django to express database lookups.

# gt means:

# greater than

# So:

# locked_until__gt=timezone.now()

# means:

# locked_until is greater than the current time.

# 19. Why does that mean "locked"?

# Imagine:

# Current time:
# 2026-09-24 11:00

# User A:

# locked_until:
# 2026-09-24 15:00

# Compare:

# 15:00 > 11:00

# Yes.

# Therefore:

# locked_until__gt=timezone.now()

# is true.

# That user is still locked until 15:00.

# But User B:

# locked_until:
# 2026-09-24 09:00

# Compare:

# 09:00 > 11:00

# No.

# So that lock has expired.

# 20. So this:
# locked=Count(
#     "id",
#     filter=Q(locked_until__gt=timezone.now())
# )

# means:

# Count users whose lock expiration time is still in the future.

# Therefore:

# stats

# might become:

# {
#     "total": 5,
#     "active": 3,
#     "locked": 1,
# }
# 21. End of aggregate

# So the complete part:

# stats = qs.aggregate(
#     total=Count("id"),
#     active=Count("id", filter=Q(is_active=True)),
#     locked=Count("id", filter=Q(locked_until__gt=timezone.now())),
# )

# is basically asking the database:

# "For this company, tell me:

# How many users are there?
# How many are active?
# How many are currently locked?"

# And Django gives you a dictionary:

# {
#     "total": 100,
#     "active": 87,
#     "locked": 4,
# }
# 22. Now pending invitations

# Next:

# pending_invitations = Invitation.objects.filter(
#     company_id=company_id, used=False
# ).count()

# Let's slow this down.

# Start:

# Invitation

# That's your Invitation model.

# Then:

# Invitation.objects

# means:

# "Give me access to the Invitation database records."

# Then:

# .filter(...)

# means:

# "Only give me invitations matching these conditions."

# 23. First filter condition
# company_id=company_id

# Same idea as before:

# Only invitations belonging to this company.

# 24. Second condition
# used=False

# This means:

# The invitation hasn't been used.

# So:

# Invitation.objects.filter(
#     company_id=company_id,
#     used=False
# )

# means:

# "Find invitations belonging to this company that haven't been used."

# 25. Then .count()
# .count()

# means:

# "How many are there?"

# For example:

# Invitation 1 → unused
# Invitation 2 → unused
# Invitation 3 → used
# Invitation 4 → unused

# The filter removes Invitation 3.

# Then:

# .count()

# returns:

# 3

# So:

# pending_invitations = 3
# 26. Now the date calculation
# since = timezone.now() - timedelta(days=30)

# This is another line worth understanding deeply.

# Start with:

# timezone.now()

# Imagine:

# 2026-09-24 11:00

# Then:

# timedelta(days=30)

# means:

# 30 days

# Then:

# timezone.now() - timedelta(days=30)

# means:

# current time - 30 days

# So approximately:

# 2026-08-25 11:00

# Therefore:

# since

# means:

# The date/time 30 days ago.

# 27. Why call the variable since?

# Because later we're going to say:

# created_at__gte=since

# which means:

# "Give me users created since this point in time."

# So:

# since
#  ↓
# 30 days ago
# 28. Now the hardest section

# Here:

# daily = (
#     qs.filter(created_at__gte=since)
#     .annotate(day=TruncDate("created_at"))
#     .values("day")
#     .annotate(count=Count("id"))
#     .order_by("day")
# )

# Don't try to understand this as one giant thing.

# It's a pipeline.

# Think:

# qs
#  ↓
# filter
#  ↓
# annotate
#  ↓
# values
#  ↓
# annotate
#  ↓
# order_by
#  ↓
# daily

# Let's walk through each stage.

# 29. Stage 1 — filter to the last 30 days
# qs.filter(created_at__gte=since)

# We already know qs contains:

# all users belonging to this company

# Now:

# created_at__gte=since

# Let's break down __gte.

# gte means:

# greater than or equal to

# So:

# created_at__gte=since

# means:

# "created_at is greater than or equal to the date 30 days ago."

# In normal English:

# Only users created within the last 30 days.

# 30. Example

# Suppose:

# since = August 25

# And users were created:

# John    August 20
# Mary    August 26
# Peter   September 1
# James   September 10

# The filter removes John because:

# August 20 < August 25

# Remaining:

# Mary
# Peter
# James

# So now our QuerySet represents:

# users from the last 30 days
# 31. Stage 2 — annotate
# .annotate(day=TruncDate("created_at"))

# This creates a calculated value called:

# day

# based on:

# created_at

# For example:

# created_at
# ---------------------
# 2026-09-20 09:32
# 2026-09-20 15:41
# 2026-09-21 08:12

# After:

# TruncDate("created_at")

# we conceptually get:

# day
# ----------
# 2026-09-20
# 2026-09-20
# 2026-09-21

# So:

# .annotate(day=TruncDate("created_at"))

# means:

# "For each record, calculate a value called day from its created_at."

# 32. Why do we need day?

# Because we're trying to answer:

# "How many people signed up each day?"

# We don't want:

# 09:32
# 15:41
# 08:12

# We want:

# September 20 → 2 users
# September 21 → 1 user

# That's why we throw away the time portion.

# 33. Stage 3 — .values("day")
# .values("day")

# This tells Django:

# "I want the results grouped/represented around the day field."

# Conceptually, instead of dealing with complete User objects:

# User
#  ├── id
#  ├── email
#  ├── company
#  ├── is_active
#  ├── created_at
#  └── ...

# we're now focusing on:

# day

# So we can group users by day.

# 34. Stage 4 — another annotate

# Now:

# .annotate(count=Count("id"))

# This means:

# "For each day, count how many user IDs belong to that day."

# Suppose after grouping we have:

# 2026-09-20 → John
# 2026-09-20 → Mary
# 2026-09-21 → Peter
# 2026-09-21 → James
# 2026-09-21 → Sarah

# Then:

# Count("id")

# produces:

# 2026-09-20 → 2
# 2026-09-21 → 3

# The resulting rows are conceptually:

# {
#     "day": date(2026, 9, 20),
#     "count": 2
# }

# {
#     "day": date(2026, 9, 21),
#     "count": 3
# }
# 35. Stage 5 — .order_by("day")
# .order_by("day")

# means:

# "Sort the results by day."

# So instead of potentially getting:

# September 21
# September 20
# September 23
# September 22

# you get:

# September 20
# September 21
# September 22
# September 23

# This is useful for a graph or dashboard.

# 36. What is daily now?

# After all those operations:

# daily = (
#     qs.filter(...)
#     .annotate(...)
#     .values(...)
#     .annotate(...)
#     .order_by(...)
# )

# daily represents something like:

# [
#     {"day": date(2026, 9, 20), "count": 2},
#     {"day": date(2026, 9, 21), "count": 3},
#     {"day": date(2026, 9, 22), "count": 1},
# ]

# Not necessarily an actual Python list yet — it's a QuerySet that will produce rows in this shape.

# 37. Now the return

# Finally:

# return {
#     **stats,
#     "pending_invitations": pending_invitations,
#     "signups_last_30_days": [
#         {"date": d["day"].isoformat(), "value": d["count"]} for d in daily
#     ],
# }

# This is another section with several concepts.

# Let's take it slowly.

# 38. **stats

# Suppose:

# stats = {
#     "total": 100,
#     "active": 80,
#     "locked": 5,
# }

# Then:

# **stats

# inside a dictionary means:

# "Take all the key/value pairs from stats and put them here."

# So:

# return {
#     **stats,
# }

# becomes conceptually:

# return {
#     "total": 100,
#     "active": 80,
#     "locked": 5,
# }

# This is called dictionary unpacking.

# 39. Then this:
# "pending_invitations": pending_invitations,

# Suppose:

# pending_invitations = 7

# Then we add:

# "pending_invitations": 7

# So now:

# {
#     "total": 100,
#     "active": 80,
#     "locked": 5,
#     "pending_invitations": 7,
# }
# 40. Now the hardest-looking part
# "signups_last_30_days": [
#     {"date": d["day"].isoformat(), "value": d["count"]} for d in daily
# ],

# This is a list comprehension.

# You can understand it by rewriting it as a normal loop.

# The original:

# [
#     {"date": d["day"].isoformat(), "value": d["count"]} for d in daily
# ]

# is roughly equivalent to:

# result = []

# for d in daily:
#     result.append({
#         "date": d["day"].isoformat(),
#         "value": d["count"],
#     })

# That version is much easier for a beginner to read.

# 41. What is d?

# Here:

# for d in daily

# d represents one row from daily.

# Suppose:

# daily

# contains:

# {"day": date(2026, 9, 20), "count": 2}
# {"day": date(2026, 9, 21), "count": 3}

# During the first loop:

# d

# is:

# {
#     "day": date(2026, 9, 20),
#     "count": 2
# }

# During the second:

# d

# is:

# {
#     "day": date(2026, 9, 21),
#     "count": 3
# }
# 42. What does d["day"] mean?

# This is a Python dictionary.

# If:

# d = {
#     "day": date(2026, 9, 20),
#     "count": 2,
# }

# then:

# d["day"]

# means:

# "Get the value stored under the key day."

# So:

# d["day"]

# gives:

# 2026-09-20
# 43. What does .isoformat() do?

# Suppose:

# d["day"]

# is a Python date:

# date(2026, 9, 20)

# Calling:

# d["day"].isoformat()

# converts it into a standard string:

# "2026-09-20"

# This is useful when returning data through an API because JSON works naturally with strings.

# 44. What does d["count"] do?

# Same dictionary concept.

# If:

# d = {
#     "day": date(2026, 9, 20),
#     "count": 2,
# }

# then:

# d["count"]

# gives:

# 2
# 45. So this:
# {"date": d["day"].isoformat(), "value": d["count"]}

# creates a new dictionary.

# For example:

# {
#     "date": "2026-09-20",
#     "value": 2
# }
# 46. Why rename day to date and count to value?

# Because the result is probably being prepared for a frontend/dashboard/chart.

# The database query gives:

# {
#     "day": date(2026, 9, 20),
#     "count": 2
# }

# But the API wants:

# {
#     "date": "2026-09-20",
#     "value": 2
# }

# This is a common pattern:

# Database representation
#         ↓
# Transform
#         ↓
# API representation
# 47. The final result

# Putting everything together, suppose:

# stats = {
#     "total": 100,
#     "active": 80,
#     "locked": 5,
# }

# and:

# pending_invitations = 7

# and:

# daily

# produces:

# {"day": date(2026, 9, 20), "count": 2}
# {"day": date(2026, 9, 21), "count": 3}

# Then the function returns:

# {
#     "total": 100,
#     "active": 80,
#     "locked": 5,
#     "pending_invitations": 7,
#     "signups_last_30_days": [
#         {
#             "date": "2026-09-20",
#             "value": 2,
#         },
#         {
#             "date": "2026-09-21",
#             "value": 3,
#         },
#     ],
# }