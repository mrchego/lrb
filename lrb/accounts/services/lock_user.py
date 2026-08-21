from __future__ import annotations
from django.db import transaction
from django.utils import timezone
from lrb.accounts.selectors.get_user import get_user
from lrb.accounts.services.ownership_guard import assert_not_last_owner
from lrb.core.exceptions import ApplicationError, ErrorCode
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lrb.accounts.models import User


@transaction.atomic
def lock_user(*, user_id: str, duration_minutes: int = 15) -> User:
    user = get_user(user_id=user_id)
    if user is None:
        raise ApplicationError("User not found.", code=ErrorCode.USER_NOT_FOUND)
    assert_not_last_owner(user=user, company_id=str(user.company_id), action="locked")
    user.locked_until = timezone.now() + timezone.timedelta(minutes=duration_minutes)
    user.save(update_fields=["locked_until"])
    return user


# 1. Purpose — Why does this exist?

# The counterpart to unlock_user. Where unlock_user clears a lock, lock_user creates one — presumably called by whatever authentication logic detects too many failed login attempts, or manually by an admin who wants to suspend access temporarily (as opposed to delete_user's permanent deactivation).

# Why is duration_minutes a parameter instead of a hardcoded constant?
# Flexibility: an automated brute-force lockout might use a short duration (15 min), while an admin manually locking a suspicious account might want hours or days. One function serves both use cases.

# 2. Imports — what's new here
# python
# from django.utils import timezone

# Django's timezone-aware alternative to Python's built-in datetime. Why not just import datetime? Because raw datetime.now() gives you "naive" time with no timezone attached — dangerous in any app with users in different timezones, or any deployment where server time and stored time could drift. timezone.now() always returns a timezone-aware datetime matching your Django settings, and timezone.timedelta is just Python's datetime.timedelta re-exported for convenience so you don't need two separate imports.

# python
# from lrb.accounts.selectors.get_user import get_user

# Notice this is different from every previous file! Earlier files had:

# python
# from lrb.accounts.selectors import get_user

# Here it's lrb.accounts.selectors.get_user — reaching one folder deeper. This tells you selectors is a package (a folder with an __init__.py), not a single selectors.py file, and inside it there's a file called get_user.py containing the function get_user. Both import lines can work — the shorter one only works if selectors/__init__.py explicitly re-exports get_user (e.g. from .get_user import get_user inside __init__.py). This isn't wrong, but it's an inconsistency across the codebase worth noting — some files import via the short path, this one uses the long path. Not a bug, but a sign of drift in convention.

# python
# from typing import TYPE_CHECKING

# if TYPE_CHECKING:
#     from lrb.accounts.models import User

# This is exactly the pattern I described in my last answer — used here for real. TYPE_CHECKING is False at runtime, so this import User line never actually executes when your program runs. It only "runs" from the perspective of static analysis tools (mypy, your IDE) pretending it's True.

# 3. Signature — where the real bug is
# python
# @transaction.atomic
# def lock_user(*, user_id: str, duration_minutes=15) -> User:

# Let's go piece by piece, including the new part.

# duration_minutes=15 — a parameter with a default value and, notice, no type hint. Every other parameter in this file family has been typed (user_id: str). This one isn't — should be duration_minutes: int = 15 for consistency. Minor, but it's the same "drift" pattern you're getting good at spotting now.

# -> User — this is the actual bug, and it's a direct consequence of the TYPE_CHECKING pattern.

# Here's the critical thing I need to walk through carefully, because it's subtle and it's exactly the trap I flagged as "the fix" in my previous answer — except this file only did half the fix.

# Function annotations are evaluated by Python at the moment the function is defined — that is, the instant Python reads the def lock_user(...) -> User: line while loading this module — unless you tell Python to postpone that evaluation.

# TYPE_CHECKING being False means the line from lrb.accounts.models import User never runs. So the name User does not exist anywhere in this file's namespace at runtime.

# Then Python hits -> User on the def line and tries to evaluate it immediately, the same way it evaluates -> str or -> int on every function. It looks for a name called User in scope. It's not there. Result:

# NameError: name 'User' is not defined

# This will crash the moment Python tries to import this module at all — not even when lock_user is called, but the instant this file is loaded anywhere in the project (e.g. Django starting up and discovering all your apps). This isn't a subtle edge-case bug; it's a hard crash on startup.

# 4. The fix — completing the pattern

# I mentioned two ways to solve this last time. This file used TYPE_CHECKING but forgot the other required half: making the annotation itself lazy, either by quoting it or by postponing evaluation file-wide.

# Option A — quote it (forward reference):

# python
# def lock_user(*, user_id: str, duration_minutes: int = 15) -> "User":

# The quotes turn User into a plain string at definition time — Python stores the literal text "User" as the annotation and never tries to look up a real name called User. Type checkers still understand this as "this returns a User" because they specifically know to interpret quoted annotations as forward references.

# Option B — the file-wide fix (this is the one I'd actually recommend, and the one this codebase is clearly reaching for but hasn't adopted consistently):

# python
# from __future__ import annotations

# Add this as literally the first line of the file (must come before other imports). It changes Python's behavior so that every annotation in the file — parameters and return types — is automatically treated as a string, deferred, never evaluated at runtime. You'd never need to manually quote anything again in this file.

# python
# from __future__ import annotations

# from django.db import transaction
# from django.utils import timezone
# from lrb.accounts.selectors.get_user import get_user
# from lrb.accounts.services.ownership_guard import assert_not_last_owner
# from lrb.core.exceptions import ApplicationError, ErrorCode
# from typing import TYPE_CHECKING

# if TYPE_CHECKING:
#     from lrb.accounts.models import User


# @transaction.atomic
# def lock_user(*, user_id: str, duration_minutes: int = 15) -> User:
#     ...

# With from __future__ import annotations at the top, the bare -> User (no quotes needed!) is now safe, because Python never actually evaluates it at runtime — it just stores it as text for tools to read later.

# 5. Body — line by line (the actual logic is solid here)
# python
# user = get_user(user_id=user_id)
# if not user:
#     raise ApplicationError("User not found.", code=ErrorCode.USER_NOT_FOUND)
# if user.company_id:
#     assert_not_last_owner(
#         user=user, company_id=str(user.company_id), action="locked"
#     )

# Correctly follows the established pattern: guard for existence, guard for ownership — and notice company_id is spelled correctly here (unlike delete_user's comapny_id typo). Good sign that typo was a one-off slip, not a systemic problem, but also proof it's worth double-checking every file rather than assuming.

# python
# user.locked_until = timezone.now() + timezone.timedelta(minutes=duration_minutes)

# Right side, inside out: timezone.timedelta(minutes=duration_minutes) creates a span of time (e.g. "15 minutes," not a specific date). timezone.now() gets the current timezone-aware moment. Adding them together produces "the current moment, plus 15 minutes" — a specific future point in time.

# Whole line: "Set this user's lock to expire 15 minutes (or however many minutes were specified) from right now."

# python
# user.save(update_fields=["locked_until"])
# return user

# Only one field saved this time (unlike unlock_user's two) — makes sense, since locking doesn't need to touch failed_login_attempts; that counter presumably gets reset separately by unlock_user or by whatever login logic triggers the lock in the first place.

# 6. Common Beginner Mistakes — this file as the case study

# ❌ Using TYPE_CHECKING without also deferring the annotation itself (via quotes or from __future__ import annotations). People often copy the if TYPE_CHECKING: block because they've seen it "solves circular imports," without understanding it only removes the import-time problem — it does nothing by itself unless the annotation is also prevented from being evaluated eagerly. Both halves are required together.

# ❌ Inconsistent import paths for the same function across files (lrb.accounts.selectors vs lrb.accounts.selectors.get_user) — not a bug, but a maintenance smell.

# ❌ Skipping a type hint on one parameter (duration_minutes=15) while typing everything else — small, but it's exactly the kind of inconsistency worth catching in review.

# 7. DIY Recipe — the rule to internalize

# Whenever you use if TYPE_CHECKING: to import something, ask immediately: "Is every annotation using this name either quoted, or is from __future__ import annotations at the top of this file?" If the answer is no, you have a guaranteed NameError waiting the moment this module gets imported — not a maybe, a certainty, because Python will hit that line no matter what code path executes.

# This is a genuinely good bug to have found — it would crash on Django startup, so you'd catch it fast in testing, but it's exactly the kind of thing worth fixing before you have six more files copying this same incomplete pattern. Want me to check the earlier files (delete_user, restore_user, promote_to_owner) for whether they're using plain from lrb.accounts.models import User — meaning they don't have this problem at all — or do you want to move on to the ownership_guard / permission-checking code next?
