from __future__ import annotations
from typing import TYPE_CHECKING
from django.db import transaction
from lrb.accounts.selectors.get_user import get_user
from lrb.accounts.services.ownership_guard import assert_not_last_owner
from lrb.core.exceptions import ApplicationError, ErrorCode

if TYPE_CHECKING:
    from lrb.accounts.models import User


@transaction.atomic
def deactivate_user(*, user_id: str) -> User:
    user = get_user(user_id=user_id)
    if user is None:
        raise ApplicationError("User Not Found", code=ErrorCode.USER_NOT_FOUND)
    assert_not_last_owner(
        user=user, company_id=str(user.company_id), action="deactivate"
    )
    user.is_active = False
    user.save(update_fields=["is_active"])
    return user


# deactivate_users — Full Walkthrough

# Four real issues in this one — let's take them in the order you'd hit them reading top to bottom, then do the full walkthrough.

# Issue 1 — the function name doesn't match what it does
# python
# def deactivate_users(*, user_id: str) -> User:

# Plural name (deactivate_users), singular everything else — one user_id parameter, one User returned. Every sibling function you've built follows singular naming for single-target actions (deactivate_user, demote_owner, force_password_reset). This should be deactivate_user. Not a runtime bug, but worth catching now — a caller skimming available functions would reasonably expect deactivate_users to accept a batch of IDs (similar to get_users_by_ids's plural shape), and be surprised to find it only takes one.

# Issue 2 — a likely-real crash: positional argument to ApplicationError
# python
# raise ApplicationError("User Not Found", ErrorCode.USER_NOT_FOUND)

# Compare this against every single prior use of this exact exception in this codebase:

# python
# raise ApplicationError("User not found.", code=ErrorCode.USER_NOT_FOUND)   # update_user
# raise ApplicationError("User Not Found", code=ErrorCode.USER_NOT_FOUND)    # force_password_reset
# raise ApplicationError("User Not Found", code=ErrorCode.USER_NOT_FOUND)    # demote_owner

# Every other call passes code= as a keyword. This one drops the keyword and passes ErrorCode.USER_NOT_FOUND positionally. Given that your project enforces keyword-only arguments as a hard convention throughout the service layer, it's highly likely ApplicationError.__init__ was written the same way — something like:

# python
# def __init__(self, message, *, code):

# If that's the case (and everything you've shown me strongly suggests it is), this line doesn't raise ApplicationError at all — it raises TypeError: __init__() takes 2 positional arguments but 3 were given the instant this branch executes, before your intended, clean error ever gets constructed. This is the same failure category as the ValidationError.message bugs from create_user — an error-handling path that itself throws the wrong error.

# Fix:

# python
# raise ApplicationError("User Not Found", code=ErrorCode.USER_NOT_FOUND)
# Issue 3 — the if user.company_id: gate is still here

# Same problem flagged last turn, now shipped into a second function: if this user has no company_id set, the entire ownership safety check is skipped, and a superuser with no company on record sails straight through to being deactivated with zero protection. My recommendation is unchanged — call assert_not_last_owner unconditionally and let its own if not user.is_superuser: return early-exit be the single place that decision gets made.

# Issue 4 — new information reveals a real design flaw in assert_not_last_owner itself

# This is worth its own careful walkthrough, because you couldn't have caught this from demote_owner alone — it only becomes visible now that we have a second caller using a different action value.

# Recall assert_not_last_owner's two messages:

# python
# f"The founder's account cannot be {action}."
# f"Cannot {action} the last active owner of the company."

# Look at what each grammatical slot actually needs:

# "cannot be {action}" — needs a past participle: "modified," "demoted," "deactivated."
# "Cannot {action} the last active owner" — needs a base verb: "modify," "demote," "deactivate."

# These are two different grammatical forms, but the code treats action as if one string could fill both. Now watch what happens with your two real call sites:

# demote_owner passes action="demoted":

# Founder message: "The founder's account cannot be demoted." ✅ correct
# Last-owner message: "Cannot demoted the last active owner of the company." ❌ grammatically broken

# deactivate_user passes action="deactivate":

# Founder message: "The founder's account cannot be deactivate." ❌ grammatically broken
# Last-owner message: "Cannot deactivate the last active owner of the company." ✅ correct

# There is no single string you can pass for action that makes both messages correct at the same time. This isn't a typo in either calling file — it's a structural flaw in assert_not_last_owner's message design that only shows up once you have two callers with genuinely different verbs to plug in. This is worth fixing at the source rather than trying to find a magic compromise word:

# python
# def assert_not_last_owner(*, user: User, company_id: str, action: str = "modified") -> None:
#     if not user.is_superuser:
#         return
#     if user.is_founder:
#         raise ApplicationError(
#             f"The founder's account cannot be {action}.",
#             code=ErrorCode.CANNOT_MODIFY_FOUNDER,
#         )
#     remaining = count_active_superusers(company_id=company_id, exclude_ids=[str(user.id)])
#     if remaining == 0:
#         raise ApplicationError(
#             f"This is the last active owner of the company and cannot be {action}.",
#             code=ErrorCode.LAST_OWNER,
#         )

# Rewording the second message to also use passive voice ("cannot be {action}", matching the first) means a single past-participle string like "demoted", "deactivated", or "modified" now correctly fills both slots. Then update your call sites to pass the past-participle form consistently: action="deactivated" instead of action="deactivate".

# Everything else in the file is structurally sound and matches the "fetch → guard → assert invariant → single-flag write" pattern you've now built several times (force_password_reset, demote_owner) — worth noting explicitly: str(user.company_id) here is a reasonable, defensive conversion given assert_not_last_owner's company_id: str hint, though it's the first file to bother converting it (earlier examples passed target.company_id unconverted) — not wrong, just inconsistent; picking one convention project-wide would be worth deciding.

# Corrected version:

# python
# from __future__ import annotations
# from typing import TYPE_CHECKING
# from django.db import transaction
# from lrb.accounts.selectors.get_user import get_user
# from lrb.accounts.services.ownership_guard import assert_not_last_owner
# from lrb.core.exceptions import ApplicationError, ErrorCode

# if TYPE_CHECKING:
#     from lrb.accounts.models import User


# @transaction.atomic
# def deactivate_user(*, user_id: str) -> User:
#     user = get_user(user_id=user_id)
#     if user is None:
#         raise ApplicationError("User Not Found", code=ErrorCode.USER_NOT_FOUND)

#     assert_not_last_owner(user=user, company_id=str(user.company_id), action="deactivated")

#     user.is_active = False
#     user.save(update_fields=["is_active"])
#     return user

# Want me to also patch demote_owner's call site to action="demoted" (already correct past-participle form, so just confirming it once assert_not_last_owner's message wording is fixed to match)?