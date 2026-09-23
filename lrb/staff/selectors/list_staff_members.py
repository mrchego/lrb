from typing import Optional

from lrb.accounts.models import User
from lrb.authorization.models.user_role import UserRole
from lrb.core.pagination import paginate_queryset


def list_staff_members(
    *,
    company_id: str,
    can_login: Optional[bool] = None,
    limit: Optional[int] = None,
    offset: int = 0,
):
    staff_ids = UserRole.objects.filter(user__company_id=company_id).values_list(
        "user_id", flat=True
    )
    qs = User.objects.select_related("company").filter(
        id__in=staff_ids, company_id=company_id
    )
    if can_login is not None:
        qs = qs.filter(can_login=can_login)
    return paginate_queryset(qs.order_by("-created_at"), limit=limit, offset=offset)


# 1. First important thing: __ in Django

# You asked about:

# user__company_id=company_id

# The __ is extremely important in Django.

# It is called double underscore lookup syntax.

# In Django ORM queries, __ lets you say:

# "Go through this relationship / field and then look at another field."

# Start with the models conceptually

# You have:

# UserRole

# and:

# User

# and apparently a User belongs to a:

# company

# So conceptually:

# UserRole
#    │
#    │ user
#    ▼
#  User
#    │
#    │ company
#    ▼
# Company

# Now look at:

# UserRole.objects.filter(
#     user__company_id=company_id
# )

# Read it from left to right:

# user
#   ↓
# company
#   ↓
# company_id

# So:

# user__company_id

# means:

# "Start from UserRole, follow its user relationship, then look at that user's company_id."

# 2. Why isn't it just company_id=company_id?

# Because company_id is apparently not a field directly on UserRole.

# Imagine your models roughly look like:

# class UserRole(models.Model):
#     user = models.ForeignKey(User, ...)
#     role = models.ForeignKey(Role, ...)

# and:

# class User(models.Model):
#     company = models.ForeignKey(Company, ...)

# The company_id belongs to User, not directly to UserRole.

# So Django lets you travel through the relationship:

# user__company_id

# Think of it as:

# UserRole
#    ↓
# user
#    ↓
# company_id
# 3. What does filter() mean here?

# You have:

# UserRole.objects.filter(
#     user__company_id=company_id
# )

# Think:

# "Give me UserRole records where the user's company ID equals the company ID I provided."

# Suppose:

# company_id = "ABC"

# Django is effectively looking for:

# UserRole
# --------------------------------
# role | user
# --------------------------------
# Admin | User 1
# Staff | User 2
# Staff | User 3

# and then checking:

# User 1 → company_id = ABC
# User 2 → company_id = XYZ
# User 3 → company_id = ABC

# It keeps:

# User 1
# User 3

# because they belong to company ABC.

# 4. Now .values_list()

# You have:

# .values_list(
#     "user_id",
#     flat=True
# )

# First understand the name:

# values_list()

# It means:

# "Instead of giving me complete model objects, give me selected field values in a list-like QuerySet."

# Without values_list()

# Suppose you do:

# UserRole.objects.filter(
#     user__company_id=company_id
# )

# Django gives you UserRole objects.

# Conceptually:

# [
#     <UserRole object>,
#     <UserRole object>,
#     <UserRole object>
# ]

# Each object contains information about the UserRole.

# But we don't actually need the whole UserRole.

# We only need:

# user_id

# So we say:

# .values_list("user_id", ...)

# Meaning:

# "I only want the user_id field from these UserRole records."

# 5. What does "user_id" mean?

# This part is another important Django concept.

# Suppose the model has:

# user = models.ForeignKey(User, ...)

# Django automatically gives you:

# user

# and also:

# user_id

# So:

# "user_id"

# means:

# "Give me the database ID of the user associated with this UserRole."

# For example:

# UserRole
# -------------------------
# id       user_id
# -------------------------
# 101      25
# 102      31
# 103      44

# Then:

# .values_list("user_id")

# asks for:

# 25
# 31
# 44
# 6. Now: what is flat=True?

# This is one of the parts that causes confusion.

# Without:

# flat=True

# you might get:

# [(25,), (31,), (44,)]

# Notice the parentheses.

# Each result is a tuple containing one value.

# Why?

# Because values_list() is designed to return rows as tuples when you ask for fields.

# So:

# .values_list("user_id")

# conceptually gives:

# [
#     (25,),
#     (31,),
#     (44,),
# ]

# But that's annoying because we only asked for one field.

# So Django gives us:

# flat=True

# which says:

# "Since I'm asking for only one field, flatten the result so I get the values directly instead of one-item tuples."

# So:

# .values_list("user_id", flat=True)

# gives:

# [
#     25,
#     31,
#     44,
# ]

# instead of:

# [
#     (25,),
#     (31,),
#     (44,),
# ]
# Easy memory trick
# values_list("user_id")
#        ↓
# [(25,), (31,), (44,)]

# values_list("user_id", flat=True)
#        ↓
# [25, 31, 44]
# 7. You asked: "The method accepts 3 parameters, why are we only implementing 2?"

# Excellent question.

# You saw:

# values_list(
#     *fields,
#     flat=False,
#     named=False
# )

# and your code has:

# .values_list(
#     "user_id",
#     flat=True
# )

# You're wondering:

# "Why don't we provide named?"

# Because Python function parameters can have default values.

# The method is conceptually defined like:

# def values_list(
#     *fields,
#     flat=False,
#     named=False
# ):

# That means:

# fields → required/variable number of fields
# flat   → optional, default = False
# named  → optional, default = False

# So if you don't provide named, Python automatically uses:

# named=False

# You are effectively doing:

# .values_list(
#     "user_id",
#     flat=True,
#     named=False
# )

# even though you don't have to write the last part.

# 8. This is the same idea as your earlier limit

# Your function has:

# def list_staff_members(
#     *,
#     company_id: str,
#     can_login: Optional[bool] = None,
#     limit: Optional[int] = None,
#     offset: int = 0,
# ):

# You don't have to provide every argument.

# For example:

# list_staff_members(company_id="ABC")

# Python automatically uses:

# can_login = None
# limit = None
# offset = 0

# because those are the defaults.

# Same concept with:

# values_list(..., flat=True)

# named has a default, so you don't need to specify it.

# 9. Now let's understand staff_ids

# The entire statement:

# staff_ids = UserRole.objects.filter(
#     user__company_id=company_id
# ).values_list(
#     "user_id",
#     flat=True
# )

# Let's translate it into plain English:

# "Find all UserRole records where the user's company is this company. From those records, give me only the user IDs."

# So conceptually:

# Company
#    │
#    ▼
# Find UserRoles belonging to this company
#    │
#    ▼
# Take their user IDs
#    │
#    ▼
# staff_ids

# For example:

# staff_ids
#     ↓
# [25, 31, 44, 52]
# 10. Now we reach the second query
# qs = User.objects.select_related("company").filter(
#     id__in=staff_ids,
#     company_id=company_id
# )

# This is another big piece.

# Let's split it.

# 11. What is qs?

# qs is just a variable name.

# It usually means:

# QuerySet

# A QuerySet is Django's representation of a collection of database records that you're asking for.

# So:

# qs = User.objects...

# means:

# "Build a query for User records and store that query in qs."

# It hasn't necessarily fetched every row immediately.

# Think of qs as instructions for what users we want.

# 12. What does User.objects mean?

# Same concept as before:

# User.objects

# is Django's database manager for the User model.

# Then:

# User.objects.filter(...)

# means:

# "Find User records matching these conditions."

# 13. What does id__in=staff_ids mean?

# This is another use of __.

# You have:

# id__in=staff_ids

# Suppose:

# staff_ids = [25, 31, 44]

# Then:

# id__in=staff_ids

# means:

# "Find users whose ID is inside this collection of IDs."

# Conceptually:

# id in [25, 31, 44]

# So Django looks for:

# User ID 25 → yes
# User ID 31 → yes
# User ID 44 → yes
# User ID 50 → no
# User ID 72 → no
# 14. Why use __in?

# Because you have multiple IDs.

# Without __in, you could do:

# id=25

# which means:

# Find the user whose ID is exactly 25.

# But:

# id__in=[25, 31, 44]

# means:

# Find users whose ID is any of these values.

# So:

# id=25

# means:

# ONE exact value

# while:

# id__in=[25,31,44]

# means:

# ANY value in this collection
# 15. Why also company_id=company_id?

# You have:

# qs = User.objects.select_related("company").filter(
#     id__in=staff_ids,
#     company_id=company_id
# )

# There are two conditions:

# 1. id must be in staff_ids
# 2. company_id must equal company_id

# Because they're both inside .filter():

# .filter(
#     id__in=staff_ids,
#     company_id=company_id
# )

# Django treats them as AND conditions.

# So conceptually:

# User ID is in staff_ids
#         AND
# User belongs to this company
# 16. Why check the company twice?

# This is an interesting design detail.

# The first query:

# UserRole.objects.filter(
#     user__company_id=company_id
# )

# finds user IDs associated with the company through UserRole.

# Then the second query:

# User.objects.filter(
#     id__in=staff_ids,
#     company_id=company_id
# )

# gets the actual User objects and also confirms that the users belong to that company.

# So the logic is roughly:

# Step 1:
# Find staff IDs belonging to Company A

#         ↓

# [25, 31, 44]

#         ↓

# Step 2:
# Find User objects whose IDs are
# 25, 31, or 44
# AND who belong to Company A

#         ↓

# Actual User objects

# This makes the intended company boundary explicit in the final User query.

# 17. Now: select_related("company")

# You asked about this too indirectly.

# User.objects.select_related("company")

# select_related() is a Django ORM optimization.

# It says:

# "When getting these User objects, also fetch their related Company data as part of the database query."

# Why?

# Imagine later you do:

# user.company.name

# Without select_related(), Django may need another database query to get the company.

# With:

# select_related("company")

# Django can fetch the user and its company together.

# Think:

# Without select_related:

# Database
#    ↓
# User
#    ↓
# later...
#    ↓
# another database query
#    ↓
# Company

# With select_related:

# Database
#    ↓
# User + Company

# It's mainly about reducing unnecessary database queries.

# 18. Now your if can_login is not None

# This part is VERY important:

# if can_login is not None:
#     qs = qs.filter(can_login=can_login)

# You asked:

# "Is this added to the first qs?"

# Yes. Exactly.

# But let's understand what "added" means.

# Initially:

# qs = User.objects.select_related("company").filter(
#     id__in=staff_ids,
#     company_id=company_id
# )

# Think of qs as:

# Users who:
#     ├── are in staff_ids
#     └── belong to this company

# Then:

# if can_login is not None:

# asks:

# "Did the caller actually give us a value for can_login?"

# 19. Why is not None?

# Because:

# can_login

# is allowed to be:

# True
# False
# None

# These have different meanings.

# can_login=True

# Means:

# "I specifically want users who can log in."

# can_login=False

# Means:

# "I specifically want users who cannot log in."

# can_login=None

# Means:

# "I don't want to filter based on login ability."

# This is why the code checks:

# if can_login is not None:

# rather than:

# if can_login:
# 20. This distinction is extremely important

# Imagine:

# can_login = False

# If you wrote:

# if can_login:

# Python would say:

# False
#  ↓
# don't enter the if

# So the filter wouldn't happen.

# But we do want to filter for False.

# That's why we use:

# if can_login is not None:

# because:

# True  → not None → enter
# False → not None → enter
# None  → is None  → don't enter

# That's exactly what we want.

# 21. What happens when can_login=True?

# Start here:

# qs = User.objects.select_related("company").filter(
#     id__in=staff_ids,
#     company_id=company_id
# )

# Suppose the database has:

# User
# ------------------------------------------------
# id    company    can_login
# ------------------------------------------------
# 10    A          True
# 11    A          False
# 12    A          True
# 13    B          True
# 14    A          False

# And:

# staff_ids = [10, 11, 12, 14]
# company_id = A
# can_login = True

# First query gives us users:

# 10
# 11
# 12
# 14

# Then:

# if can_login is not None:

# Since:

# True is not None

# is true, we execute:

# qs = qs.filter(can_login=can_login)

# Because can_login=True, that becomes conceptually:

# qs = qs.filter(can_login=True)

# Now the results become:

# 10 → True  ✅
# 11 → False ❌
# 12 → True  ✅
# 14 → False ❌

# So the final users are:

# 10
# 12
# 22. What happens when can_login=False?

# Suppose:

# can_login = False

# The condition:

# if can_login is not None:

# is still true.

# Because:

# False is not None
#       ↓
#      True

# Then:

# qs = qs.filter(can_login=can_login)

# becomes:

# qs = qs.filter(can_login=False)

# Now you get:

# 11 → False ✅
# 14 → False ✅

# So:

# can_login=True
#     ↓
# only login-enabled users

# can_login=False
#     ↓
# only non-login users
# 23. What happens when can_login=None?

# Now:

# can_login = None

# The condition:

# if can_login is not None:

# is false.

# So this does not execute:

# qs = qs.filter(can_login=can_login)

# Therefore the original qs remains:

# User.objects.select_related("company").filter(
#     id__in=staff_ids,
#     company_id=company_id
# )

# Meaning:

# Give me all the staff members for this company, regardless of whether they can log in.

# 24. So yes — you're right about qs

# You asked:

# "is added to the first qs"

# Yes.

# Think of it like building a query step by step.

# First:

# qs = User.objects.select_related("company").filter(
#     id__in=staff_ids,
#     company_id=company_id
# )

# You have:

# qs
#  ↓
# Users in this company
# who are in staff_ids

# Then if can_login=True:

# qs = qs.filter(can_login=True)

# Now:

# qs
#  ↓
# Users in this company
# AND
# users in staff_ids
# AND
# can_login = True

# You're reassigning qs to a more restricted QuerySet.

# 25. This is NOT creating a completely unrelated query

# This:

# qs = qs.filter(can_login=can_login)

# is based on the existing:

# qs

# That's why the previous conditions remain.

# You can mentally visualize it as:

# Original qs
#     │
#     ├── company_id = A
#     │
#     └── id in staff_ids
#              │
#              ▼
#        filter(can_login=True)
#              │
#              ▼
#         final qs
# 26. Now order_by("-created_at")

# You asked:

# "Where does order_by come from?"

# It comes from Django's QuerySet API.

# You didn't create order_by() yourself.

# Django provides it.

# Because:

# qs

# is a QuerySet, you can call QuerySet methods on it.

# For example:

# qs.filter(...)
# qs.order_by(...)
# qs.select_related(...)
# qs.values(...)

# These are methods provided by Django's ORM.

# 27. What does order_by() do?

# It controls the order of the results.

# You have:

# qs.order_by("-created_at")

# The field is:

# created_at

# The minus sign:

# -

# means:

# descending order

# So:

# "-created_at"

# means:

# newest created users first.

# Without -
# qs.order_by("created_at")

# means ascending:

# oldest
#   ↓
# 2026-01-01
# 2026-02-01
# 2026-03-01
# 2026-04-01

# With:

# qs.order_by("-created_at")

# you get:

# newest
#   ↓
# 2026-04-01
# 2026-03-01
# 2026-02-01
# 2026-01-01

# So the - has nothing to do with subtraction here.

# It's Django's syntax for descending order.

# 28. Finally: paginate_queryset()

# You have:

# return paginate_queryset(
#     qs.order_by("-created_at"),
#     limit=limit,
#     offset=offset
# )

# Notice something important.

# The first argument is:

# qs.order_by("-created_at")

# So you're giving paginate_queryset() the final QuerySet.

# Then:

# limit=limit

# passes the function's limit value.

# And:

# offset=offset

# passes the function's offset value.

# 29. What does paginate_queryset expect?

# You showed its definition:

# def paginate_queryset(
#     queryset: Any,
#     *,
#     limit: Any | None = None,
#     offset: int = 0
# ) -> tuple[list, Any]

# Let's decode that.

# First parameter
# queryset

# This receives:

# qs.order_by("-created_at")

# So:

# queryset
#     ↓
# final User QuerySet
# Second parameter
# limit

# This receives:

# limit=limit

# For example:

# limit=20

# means:

# Return at most 20 records.

# Third parameter
# offset

# This receives:

# offset=40

# meaning:

# Skip the first 40 records and start from there.

# 30. Example of pagination

# Suppose there are 100 users.

# You call:

# paginate_queryset(
#     qs,
#     limit=20,
#     offset=40
# )

# Conceptually:

# Users:

# 1
# 2
# 3
# ...
# 40   ← skip these
# 41
# 42
# ...
# 60   ← return these
# 61
# ...
# 100

# So:

# offset = 40
# limit = 20

# means:

# Skip 40 and return the next 20.

# 31. Why return directly?

# Your function ends with:

# return paginate_queryset(
#     qs.order_by("-created_at"),
#     limit=limit,
#     offset=offset
# )

# So list_staff_members() doesn't take the pagination result and store it in another variable.

# It simply says:

# "Call paginate_queryset() and return whatever it gives me."

# If paginate_queryset() returns:

# (items, total_count)

# then list_staff_members() returns that same pair.

# For example:

# (
#     [User1, User2, User3],
#     57
# )

# Meaning:

# items       → current page
# total_count → total matching users
# 32. Put the whole function together

# Now let's read the function like a programmer.

# def list_staff_members(
#     *,
#     company_id: str,
#     can_login: Optional[bool] = None,
#     limit: Optional[int] = None,
#     offset: int = 0,
# ):

# Define a function for listing staff members. We must provide a company ID. Optionally, we can filter by login ability and pagination.

# Then:

# staff_ids = UserRole.objects.filter(
#     user__company_id=company_id
# ).values_list(
#     "user_id",
#     flat=True
# )

# Find UserRole records whose user's company is this company, and extract only their user IDs as a flat list-like QuerySet.

# Then:

# qs = User.objects.select_related("company").filter(
#     id__in=staff_ids,
#     company_id=company_id
# )

# Find User objects whose IDs are in those staff IDs and whose company is this company. Also fetch their company relationship efficiently.

# Then:

# if can_login is not None:

# Did the caller specifically ask for True or False?

# If yes:

# qs = qs.filter(can_login=can_login)

# Narrow the existing QuerySet to users matching that login value.

# Then:

# return paginate_queryset(
#     qs.order_by("-created_at"),
#     limit=limit,
#     offset=offset
# )

# Sort the final users from newest to oldest, paginate them, and return the pagination result.

# 33. The complete mental picture

# This is probably the most useful way to remember the function:

#                   company_id
#                       │
#                       ▼
#              ┌─────────────────┐
#              │    UserRole      │
#              └─────────────────┘
#                       │
#                 user__company_id
#                       │
#                       ▼
#               Get user_id values
#                       │
#                       ▼
#                staff_ids
#               [12, 15, 21, 30]
#                       │
#                       ▼
#              ┌─────────────────┐
#              │      User       │
#              └─────────────────┘
#                       │
#              id__in=staff_ids
#                       │
#              company_id=company_id
#                       │
#                       ▼
#                   qs
#                       │
#                       │
#              can_login provided?
#                  /          \
#                YES           NO
#                 │             │
#                 ▼             │
#        qs.filter(             │
#          can_login=...        │
#        )                      │
#                 │             │
#                 └──────┬──────┘
#                        ▼
#              order_by("-created_at")
#                        │
#                        ▼
#               paginate_queryset()
#                        │
#                        ▼
#              (items, total_count)
# The 5 Django concepts to remember
# Code	Think of it as
# user__company_id	Follow user → look at company_id
# values_list("user_id")	Give me only this field's values
# flat=True	Don't wrap each single value in a tuple
# id__in=staff_ids	ID is one of these IDs
# order_by("-created_at")	Newest created_at first

# And the most important concept in the middle is:

# qs = qs.filter(can_login=can_login)

# This doesn't throw away the previous query. You're taking the existing QuerySet and adding another condition to it:

# company condition
#        +
# staff ID condition
#        +
# can_login condition
#        ↓
# final QuerySet

# That's the pattern you'll see all over Django.