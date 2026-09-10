from django.db import IntegrityError, transaction
from lrb.accounts.selectors.get_user import get_user
from lrb.authorization.models.role import Role
from lrb.authorization.models.user_role import UserRole
from lrb.authorization.selectors.get_user_permissions import (
    invalidate_user_permissions_cache,
)
from lrb.core.exceptions import ApplicationError, ErrorCode


@transaction.atomic
def assign_role(*, user_id, role_id, company_id):
    user = get_user(user_id=user_id)
    if not user or str(user.company_id) != str(company_id):
        raise ApplicationError(message="User not found.", code=ErrorCode.USER_NOT_FOUND)

    role = Role.objects.filter(pk=role_id, company_id=company_id).first()
    if not role:
        raise ApplicationError(message="Role not found.", code=ErrorCode.ROLE_NOT_FOUND)

    try:
        UserRole.objects.create(user=user, role=role)
    except IntegrityError:
        raise ApplicationError(
            message="This user is already assigned to this role.",
            code=ErrorCode.ALREADY_ASSIGNED,
        )

    invalidate_user_permissions_cache(user_id=user.id)
    return True


# Teaching: assign_role

# This one reuses everything you've learned — @transaction.atomic, scoped lookups, IntegrityError catching from create_role — except there's a real bug in this file, and part of learning to read code is learning to catch that kind of thing yourself. I'll walk through it normally, then stop hard on the bug, because it's exactly the kind of thing your project convention asks you to catch.

# 1. What is it?

# A service that assigns an existing role to an existing user — validating both belong to the same company, creating the join record, and invalidating a permissions cache. New pieces: importing a selector from another app (get_user), and str(user.company_id) != str(company_id).

# 2. How is it written?

# from lrb.accounts.selectors.get_user import get_user
# This function reaches across app boundaries — authorization importing a selector from accounts. This is expected and fine: selectors are meant to be reused across your project wherever that data is needed; authorization needs to know about users, so it borrows the accounts app's own read logic rather than querying the User model directly itself.

# user = get_user(user_id=user_id)
# Straightforward — same "selector returns object or None" shape you learned with get_permission.

# if not user or str(user.company_id) != str(company_id):
# Two checks joined by or, same short-circuit safety as get_current_user_or_raise from your very first file: not user is checked first, so if the user doesn't exist at all, Python never tries to read .company_id off of None (which would crash).

# The second check, str(user.company_id) != str(company_id), is new: both sides get wrapped in str(...) before comparing. Why? Because company_id might come in as different types depending on where it originated — user.company_id (from the database, possibly a UUID object) versus company_id (the function's incoming argument, possibly already a plain string, from GraphQL input). Comparing a UUID object directly to a string with != would always be considered "not equal" even if they represent the exact same value, because Python compares type and value for equality by default. Converting both sides to str first guarantees you're comparing them on equal footing — a defensive normalization step, similar in spirit to why the mutations file wrapped current.company_id in str(...) before passing it into bulk services.

# UserRole.objects.create(user=user, role=role)
# Same .create() pattern as create_role — build and save a new UserRole row (the join/assignment record) in one call, linking this user to this role.

# except IntegrityError:
# Same reasoning as create_role: rather than checking "is this user already assigned to this role?" beforehand (a race-condition-prone check-then-act), the code just attempts the insert and relies on a database-level uniqueness constraint (probably unique_together = ("user", "role") on UserRole) to reject a duplicate assignment, catching that failure here.

# 3. Signature — broken into pieces
# python
# def assign_role(*, user_id, role_id, company_id):
# Piece	Meaning
# *,	all keyword-only
# user_id	required — who to assign
# role_id	required — which role
# company_id	required — the scope both user and role must belong to

# No type hints, no return hint — same drift pattern you've now correctly flagged in every service so far.

# 4. Body — line by line
# python
# user = get_user(user_id=user_id)
# if not user or str(user.company_id) != str(company_id):
#     raise ApplicationError(message="User not found.", code=ErrorCode.USER_NOT_FOUND)

# Fetch the user; reject if missing or if they belong to a different company than the one performing this assignment — same "wrong company = not found" security principle as get_role.

# python
# role = Role.objects.filter(pk=role_id, company_id=company_id).first()
# if not role:
#     raise ApplicationError(message="Role not found.", code=ErrorCode.ROLE_NOT_FOUND)

# Same pattern, for the role.

# python
# try:
#     UserRole.objects.create(user=user, role=role)
# except IntegrityError:
#     return ApplicationError(message=IntegrityError, code=ErrorCode.ALREADY_ASSIGNED)

# Attempt to create the assignment. This line has two real bugs — see section 5, this is the important part of this file.

# python
# invalidate_user_permissions_cache(user_id=user.id)
# return True

# If the assignment succeeded, clear this specific user's cached effective-permissions (not the whole role's cache like update_role did — makes sense, since only this one user's permissions changed, not everyone with the role), and signal success.

# 5. Why? — and where this file actually breaks its own pattern

# I want to slow down here, because this is exactly the kind of thing you said you want to catch, and it's a genuinely instructive bug (or pair of bugs).

# Bug 1: return ApplicationError(...) instead of raise ApplicationError(...)

# Look at every single not-found check earlier in this same function:

# python
# raise ApplicationError(message="User not found.", code=ErrorCode.USER_NOT_FOUND)
# raise ApplicationError(message="Role not found.", code=ErrorCode.ROLE_NOT_FOUND)

# Both raise. But in the except IntegrityError: block:

# python
# return ApplicationError(message=IntegrityError, code=ErrorCode.ALREADY_ASSIGNED)

# This says return, not raise. The consequence: instead of throwing an error that stops execution and gets caught by the calling resolver's except ApplicationError as e: block (as you saw in UserMutation), this function just hands back an ApplicationError object as if it were a normal, successful return value — like returning a Role or True. The calling resolver, expecting either a real result or a raised exception, would receive this exception object as if it succeeded, and likely try to use it as if it were the expected data — which would break in confusing ways downstream, or silently produce nonsense (e.g., a SimpleMutationPayload(success=True) being built around an error object). This is precisely the failure mode _or_raise-style functions and your project's try/except ApplicationError convention are designed to prevent — and this line breaks that contract.

# Bug 2: message=IntegrityError — passing the exception class, not a message string

# Every other error message in this whole file (and every file you've read) has been a human-readable string: "User not found.", f"Unknown permission codename(s): {...}". Here, message=IntegrityError passes the class itself — the raw Python exception type object, not even an instance of it (note: no parentheses, so it's not even calling it), and definitely not a string describing what went wrong. If this ever reached a user-facing error message, it would render as something like <class 'django.db.utils.IntegrityError'> — meaningless and unprofessional, breaking the "friendly business-level message" goal that create_role's IntegrityError-catching was built around achieving in the first place.

# What the corrected line should almost certainly look like:

# python
# except IntegrityError:
#     raise ApplicationError(
#         message="This user is already assigned to this role.",
#         code=ErrorCode.ALREADY_ASSIGNED,
#     )

# This is a great real example of why comparing a function against the pattern established by its siblings (which you've been doing this whole conversation) is such a powerful reading technique — the bug isn't obvious in isolation, but it's glaring the moment you notice every sibling function in this file, and every prior file, uses raise with a real string message in this exact situation.

# 6. Connections

# What comes in: user_id, role_id, and company_id — the scope both must share.
# What goes out (when correct): True, or an ApplicationError raised for "not found" (either side) or "already assigned."
# Where this fits: the assignment-side counterpart to delete_role's guard (role.user_roles.exists()) — this is the function that creates the UserRole rows that delete_role later checks for before allowing a role to be removed.
# Cache connection: confirms there isn't just one shared "role permissions" cache (from update_role) — there's also a per-user permissions cache, invalidated here specifically because assigning a new role changes what permissions this one user effectively has, without necessarily affecting anyone else who has the same role.

# 7. Advanced concepts

# A) return vs raise — why mixing them up is a serious, easy-to-miss class of bug
# return says "here is my successful result, hand it to whoever's waiting for it." raise says "something went wrong, stop normal execution, and let this propagate up until something explicitly catches it." An object being an instance of an exception class does not automatically make Python treat it as an error if you return it — Python only treats something as an error-in-progress when you use the raise keyword. This is a common category of real-world bug: constructing the right error object, but forgetting the keyword that actually triggers error-handling behavior. Worth building a habit of double-checking: whenever you write SomeError(...), ask "does this line start with raise?"

# B) Passing a class where a value was expected
# message=IntegrityError (no parentheses) refers to the class itself as an object — classes are themselves values in Python, which is why this doesn't cause an immediate crash; it's technically legal Python, just semantically wrong here. This is subtly different from IntegrityError() (which would create an instance) or str(IntegrityError) (which would at least produce readable text like "<class '...'>"). None of these were intended — a plain descriptive string was needed, and none was written.

# 8. Small example (demonstrating the actual bug)
# python
# class ApplicationError(Exception):
#     def __init__(self, message):
#         self.message = message

# def broken_assign():
#     try:
#         raise ValueError("duplicate")
#     except ValueError:
#         return ApplicationError(message="Already assigned")   # BUG: should be raise

# result = broken_assign()
# print(type(result))    # <class 'ApplicationError'> — looks like it "worked"!
# print(result.message)  # "Already assigned" — but no exception was ever raised

# # Meanwhile, calling code expecting a real result or a raised error:
# try:
#     outcome = broken_assign()
#     print("Success:", outcome)   # this branch runs! Nothing was ever caught.
# except ApplicationError as e:
#     print("Failed:", e.message)  # this branch NEVER runs — the bug's real damage

# This is exactly why the bug is dangerous: the code doesn't crash loudly. It quietly produces a result that looks plausible but breaks the error-handling contract every calling resolver relies on.

# 9. What you should remember
# raise and return are not interchangeable, even when the value being handed back is an exception instance. Only raise actually triggers Python's error-propagation and gets caught by a matching except block; return-ing an exception object just passes it along as ordinary data.
# When you spot an exception being constructed, check for the raise keyword in front of it — a missing raise is a real, subtle, project-breaking bug, and it's exactly the kind of thing that's easy to miss in review unless you're specifically comparing it against how the rest of the codebase does the same thing.
# Error messages should always be human-readable strings, not raw exception classes or objects — message=IntegrityError fails that basic contract; message="This user is already assigned to this role." is what every sibling error in this codebase does.
# Comparing a function against its own siblings (or against itself, earlier in the same function) is one of the most reliable ways to catch bugs while reading real code — this bug was invisible in isolation, but obvious next to the two correctly-written raise statements two lines above it.
# str(a) != str(b) is a normalization trick for comparing values that might come from different type sources (a database UUID vs. a plain string) — recognize this pattern whenever equality checks span "data from the database" vs. "data from an external request."
