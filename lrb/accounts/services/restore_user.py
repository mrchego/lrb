from __future__ import annotations
from django.db import transaction
from lrb.accounts.selectors.get_user import get_user
from lrb.core.exceptions import ApplicationError, ErrorCode
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lrb.accounts.models import User


@transaction.atomic
def restore_user(*, user_id: str) -> User:
    user = get_user(user_id=user_id)
    if not user:
        raise ApplicationError("User not found.", code=ErrorCode.USER_NOT_FOUND)
    user.is_active = True
    user.can_login = True
    user.save(update_fields=["is_active", "can_login"])
    return user


# 1. Purpose — Why does this exist?

# delete_user sets is_active = False and can_login = False. This function is its mirror image — it flips both back to True. It's the "undo" button for a soft-delete.

# Why do you need this as a separate function instead of just calling delete_user again with different values?
# Because delete_user also runs assert_not_last_owner — logic that only makes sense when removing access, not restoring it. If restore_user reused delete_user with a flag like delete_user(user_id=..., restore=True), you'd end up with one function doing two unrelated jobs, with branching logic inside to handle each — messier and more error-prone than just having two small, single-purpose functions.

# When would this be used in a real project?
# An admin panel "Reactivate User" button, or a "cancel deletion" action within some grace period before a soft-deleted user is ever hard-deleted for real.

# 2. Imports

# Identical to delete_user's imports, minus ownership_guard — and that omission is meaningful, not accidental. Let's confirm why in the body.

# 3. Signature
# python
# @transaction.atomic
# def restore_user(*, user_id: str) -> User:

# Nothing new versus the last two files — same shape: atomic transaction, keyword-only user_id, returns a User. At this point you shouldn't need this section re-explained; you should be able to read this line cold. (If you can — that's the whole point of your framework working.)

# 4. Body — line by line
# python
# user = get_user(user_id=user_id)
# if not user:
#     raise ApplicationError("User not found.", code=ErrorCode.USER_NOT_FOUND)

# Correct guard clause, present this time — matches delete_user, unlike the buggy unlock_user. This is the shape every function starting with get_user() in this codebase should follow.

# python
# user.is_active = True
# user.can_login = True
# user.save(update_fields=["is_active", "can_login"])
# return user

# Exact structural mirror of delete_user's final block, with the booleans flipped and update_fields targeting the same two columns.

# 5. Design Discussion — the interesting question

# Why doesn't restore_user call assert_not_last_owner?

# Think about what that guard actually protects against: a company being left with zero owners. Restoring a user adds someone back with (presumably) their prior permissions — it can only ever increase the number of active people attached to a company, never decrease it. There's no way restoring someone creates an ownerless company. So the guard would be dead code here — checked, but structurally incapable of ever failing.

# Is there a guard restore_user is missing that it should have?

# Worth asking: what if the user being restored belongs to a company that itself was deleted/deactivated in the meantime? Restoring the user might silently reactivate someone whose company no longer exists in a valid state. Whether that matters depends on business rules you'd know better than I would — but it's the right kind of question to ask any time you see one function in a pair have a check the other lacks. Sometimes the asymmetry is correct (as it is here with ownership), and sometimes it's a gap (as it was in unlock_user). The skill is learning to tell which is which by reasoning about what the guard actually protects against, not just pattern-matching "the sibling function has a check, so this one needs it too."

# 6. Common Beginner Mistakes

# ❌ Assuming "restore" is always the exact logical inverse of "delete" and therefore needs the exact same guards run in reverse. Deletion and restoration often have asymmetric risk profiles — deletion can violate invariants (ownerless company) that restoration structurally cannot.

# ❌ Copy-pasting delete_user to make restore_user, flipping the booleans, but forgetting to also remove the now-irrelevant assert_not_last_owner call — leaving dead, confusing code that makes a future reader wonder "wait, can restoring someone also fail an ownership check?"

# 7. Pattern Recognition — the family of three

# You can now see the actual template this codebase uses for every "toggle a user's state" service:

# python
# @transaction.atomic
# def <verb>_user(*, user_id: str) -> User:
#     user = get_user(user_id=user_id)
#     if not user:
#         raise ApplicationError("User not found.", code=ErrorCode.USER_NOT_FOUND)

#     [any state-specific guard, e.g. assert_not_last_owner]

#     user.<field_a> = <new_value>
#     user.<field_b> = <new_value>
#     user.save(update_fields=["<field_a>", "<field_b>"])
#     return user

# Once you internalize this shape, you don't need me to explain the next one line-by-line — you can predict it, then just scan for the two things that vary: which fields change, and what domain-specific guard (if any) belongs in the middle. That's exactly what your document's "General Pattern Recognition" section is pointing at — and it's also why unlock_user's missing guard stood out immediately: it broke a pattern you now know cold.

# 8. Real Project Usage

# Paired with delete_user behind something like a PATCH /users/<id>/restore/ endpoint, gated by a permission check (this is where the actual RBAC layer of your project will hook in — checking "does the caller have can_restore_users permission" before this service function ever runs).

# You now have three files in this "user lifecycle" family down cold, including one real bug caught by pattern comparison. Want to keep this family going (there's likely a suspend_user or change_role next), or pivot to the actual role/permission-checking code — the decorators or middleware that decide who's allowed to call these functions in the first place? That's where this project's RBAC identity really lives.
