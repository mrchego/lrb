from __future__ import annotations
from django.db import transaction
from lrb.accounts.selectors.get_user import get_user
from lrb.core.exceptions import ApplicationError, ErrorCode
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lrb.accounts.models import User


@transaction.atomic
def force_password_reset(*, user_id: str) -> User:
    user = get_user(user_id=user_id)
    if user is None:
        raise ApplicationError("User Not Found", code=ErrorCode.USER_NOT_FOUND)
    user.password_reset_required = True
    user.save(update_fields=["password_reset_required"])
    return user

# 1. Purpose — Why this exists

# What problem is this solving?
# Sometimes a user's password needs to be reset not by the user themselves, but by an administrative action — a staff member suspects a compromised account, or a security policy requires periodic resets. Rather than actually changing the password here, this function flags the account so that on next login (or next request), some other part of the system knows: "this user must set a new password before doing anything else."

# Why not just set user.password_reset_required = True directly wherever this is needed?
# Same reasoning as every service you've reviewed — centralizing the lookup, the not-found handling, and the save logic in one place means every caller gets consistent behavior, and the field name itself only needs to be known in one location.

# When is this used?
# A staff "force password reset" action on a user management screen — likely triggered after a suspected security incident, or as part of an onboarding/offboarding flow.

# What breaks without it?
# Scattered direct field assignments across the codebase, each one potentially forgetting update_fields, or duplicating the same not-found handling.

# 2. Imports — explained like you've never programmed
# python
# from __future__ import annotations
# from django.db import transaction
# from lrb.accounts.selectors.get_user import get_user
# from lrb.core.exceptions import ApplicationError, ErrorCode
# from typing import TYPE_CHECKING

# if TYPE_CHECKING:
#     from lrb.accounts.models import User

# Everything here you've now seen before, so let's move through it as recognition rather than fresh explanation:

# from __future__ import annotations — makes every annotation in this file behave as a string automatically, letting -> User work without needing User to exist at runtime.
# from django.db import transaction — same @transaction.atomic tool from create_user/update_user.
# from lrb.accounts.selectors.get_user import get_user — this is the direct submodule import style from your architecture question two turns ago, not the from lrb.accounts.selectors import get_user re-export style. Consistent with the recommendation to minimize what gets pulled in per import.
# ApplicationError, ErrorCode — the same "not found" exception type used in update_user.
# TYPE_CHECKING + the guarded User import — exactly the pattern from the last three questions, correctly applied here since User is annotation-only in this file.

# One small ordering note, not a bug: convention (and tools like isort) typically place standard-library imports (from typing import TYPE_CHECKING) before third-party/Django imports (from django.db import transaction), which are in turn before your own project's imports. Here, typing is listed last, after your own lrb.core.exceptions. Won't cause any error, but worth tidying for consistency with the rest of your codebase.

# 3. Signature — every symbol explained
# python
# @transaction.atomic
# def force_password_reset(*, user_id: str) -> User:

# Nothing new mechanically — @transaction.atomic because this does a read (get_user) and a write (save) that should succeed or fail together; * for keyword-only; user_id: str as the one required parameter; -> User as the confident "always returns a real user, always raises on failure" promise, matching the pattern from update_user.

# 4. Classes

# No class defined here. User is referenced only as a type (and only behind TYPE_CHECKING, as established) — never instantiated in this file at all, since get_user already hands back an existing instance rather than this function needing to build one.

# 5. Body — line by line
# python
# user = get_user(user_id=user_id)
# if user is None:
#     raise ApplicationError("User Not Found", code=ErrorCode.USER_NOT_FOUND)

# Identical shape to the fetch-and-guard block at the top of update_user — reusing the same selector, the same None check, the same ApplicationError type for "this ID doesn't correspond to a real user."

# One small inconsistency worth flagging: the message here is "User Not Found" (title case), while update_user's equivalent line used "User not found." (sentence case, trailing period). Not a bug — the error code (ErrorCode.USER_NOT_FOUND) is what matters for programmatic handling — but if a frontend ever displays these raw strings directly rather than mapping the error code to its own translated message, this inconsistency would show up as visibly different wording for the exact same underlying condition.

# python
# user.password_reset_required = True

# Direct attribute assignment on the already-fetched, in-memory object — same mechanism as every field assignment you've seen in update_user. password_reset_required is presumably a boolean field on your User model that some other part of your auth flow checks (likely right after login, forcing a redirect to a "set new password" screen before allowing anything else).

# python
# user.save(update_fields=["password_reset_required"])

# This is new — worth its own full breakdown. In every prior file, you've seen user.save() with no arguments. Here, update_fields=["password_reset_required"] is being passed in.

# By default, .save() with no arguments writes every field on the model back to the database, in one UPDATE statement covering every column. update_fields narrows that down: "only write this specific column, ignore every other field on this object, even if some of them happen to differ from what's in the database."

# Why does that distinction matter here specifically? Two real reasons: (1) efficiency — updating one boolean column is a smaller, faster write than rewriting every field on the user row; (2) safety against stale data. Since this function only fetched user via get_user and touched one field, there's no reason to risk overwriting other fields with whatever values happened to be loaded into this particular object — if some other process modified this same user's email or phone in the tiny window between this function's fetch and its save, a full unguarded .save() could silently clobber that other change back to whatever was loaded here. update_fields guarantees this function only ever touches the one column it actually meant to change.

# Also notice: no full_clean() before this save, unlike create_user and update_user. That's a deliberate, sensible omission worth naming explicitly rather than assuming it's missing by accident — full_clean() validates the entire model, including fields this function never touches and has no intention of changing. Since only one boolean field is being set here, running full model validation would be unnecessary overhead, and could even fail on unrelated pre-existing data problems having nothing to do with this specific action.

# python
# return user

# Return the same in-memory object, now updated — no need to re-fetch, since the object was mutated in place.

# 6. Beginner questions, answered proactively

# Why not just write user.save() with no arguments, like create_user and update_user do?
# Because those two functions are setting up or changing several fields at once — a full save makes sense there, since most of the object's fields are meaningfully part of "what's being created/updated." Here, exactly one field is changing, and update_fields documents that precisely, at the same time as making the actual database write cheaper.

# Does update_fields skip full_clean()-style validation on that one field?
# update_fields only affects what .save() writes to the database — it has nothing to do with .full_clean(), which is a completely separate, optional step this function simply chose not to call. Given that password_reset_required is a simple boolean with no format to validate, skipping full_clean() here isn't cutting a safety corner — there's nothing meaningful to validate.

# Why is there no IntegrityError/ValidationError handling here like in create_user/update_user?
# Because those exception blocks in the earlier files existed specifically to catch email uniqueness problems — a duplicate-email business rule violation. This function never touches email, and setting a boolean to True on an existing, already-valid row has essentially no way to violate a uniqueness or format constraint. The absence of that error-handling block isn't an oversight; it correctly reflects that this specific write can't fail in those particular ways.

# 7. Design discussion

# Why does this function exist as its own tiny, single-purpose service rather than folding into update_user?
# Because password_reset_required is a security-relevant flag, not a general "profile info" field — the same reasoning that kept password, is_staff, and friends out of update_user's signature entirely. Keeping this as its own dedicated function means a resolver granting access to "edit basic profile" permissions can never accidentally also expose the ability to force a password reset — that requires a separate, specifically-granted permission on whatever resolver calls this function.

# Trade-off: this does mean more small, single-purpose functions to maintain overall, rather than one flexible "update anything" function. That's the same trade-off you've seen throughout this project's service layer — narrow, explicit functions over broad, generic ones — and it's a consistent, deliberate choice, not an accident of how this particular file was written.

# 8. DIY Recipe — build one like this yourself
# Fetch via a selector, guard against None — same shape every time a service needs to act on a specific existing record.
# For a single-field flag change, skip full_clean() if there's genuinely nothing to validate about that one field — don't add ceremony that doesn't protect anything.
# Use update_fields=[...] whenever you're only changing one or a few fields on an object that might have other fields loaded — it's both a performance and a correctness improvement over a full unguarded save.
# Keep security-sensitive single-purpose actions as their own dedicated functions, even when they'd technically fit inside a more general update function — so permission checks stay narrow and precise at the resolver layer.
# 9. General pattern recognition

# This is a "single-flag action" pattern — a lighter-weight cousin of the full "fetch, mutate, validate, save" shape from update_user:

# python
# @transaction.atomic
# def <verb>_<thing>(*, <thing>_id: str) -> Model:
#     obj = get_<thing>(<thing>_id=<thing>_id)
#     if obj is None:
#         raise ApplicationError(...)
#     obj.<flag_field> = <new_value>
#     obj.save(update_fields=["<flag_field>"])
#     return obj

# You'll see this same shape for things like lock_account, verify_email, mark_onboarding_complete — anywhere a single boolean or status field needs to flip, without the overhead of a full multi-field update.

# 10. Real project usage
# python
# def resolve_force_password_reset(self, info, user_id: str) -> UserPayload:
#     actor = get_current_user(info)
#     require_permission(actor=actor, codename="staff.force_password_reset")
#     try:
#         user = force_password_reset(user_id=user_id)
#     except ApplicationError as e:
#         return UserPayload(success=False, errors=[e.to_error_response()])
#     return UserPayload(success=True, user=user)

# Notice the permission codename here is deliberately narrow and specific (staff.force_password_reset), not the broader staff.edit_users used for update_user — exactly the access-control precision this function's separateness is designed to enable.

# 11. Common beginner mistakes

# ❌ Calling .save() with no arguments here "just to be safe" — actually the less safe option, since it risks overwriting other fields on the object with stale in-memory values if anything else modified this row concurrently.

# ❌ Forgetting update_fields matters for more than performance — treating it as a pure optimization when it's also a correctness guard against clobbering concurrent changes.

# ❌ Adding full_clean() reflexively to match create_user/update_user, without asking whether there's actually anything meaningful to validate for this specific change.

# ❌ Folding this logic into update_user for convenience, losing the ability to grant this specific capability independently via its own permission codename.

# 12. Think like the original developer
# What problem am I solving? "Staff need to flag an account as requiring a password reset, without touching anything else about that user, and without this being bundled into general profile editing."
# What inputs will I need? Just the user's ID — nothing else about the write depends on any other input.
# What could go wrong? The ID doesn't correspond to a real user; a full unguarded save could clobber unrelated concurrent changes to the same row.
# How should I report failure? The same ApplicationError/USER_NOT_FOUND vocabulary already established for "record doesn't exist" across the codebase.
# What should happen if everything works? Flip exactly one field, write exactly that one field back to the database, and return the updated object — no more, no less.


