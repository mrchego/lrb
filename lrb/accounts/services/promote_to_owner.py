from django.db import transaction
from lrb.accounts.models import User
from lrb.accounts.selectors import get_user
from lrb.core.exceptions import ApplicationError, ErrorCode


@transaction.atomic
def promote_to_owner(*, user_id: str) -> User:
    user = get_user(user_id=user_id)
    if not user:
        raise ApplicationError("User Not Found.", code=ErrorCode.USER_NOT_FOUND)
    if user.is_superuser:
        raise ApplicationError("User is already owner", code=ErrorCode.VALIDATION_ERROR)
    user.is_superuser = True
    user.is_staff = True
    user.save(update_fields=["is_superuser", "is_staff"])
    return user


# 1. Purpose — Why does this exist?

# This promotes a regular user to "owner" status. In Django, is_superuser and is_staff are built-in fields on the default user model (or anything inheriting from it) — not something this project invented. So this function is repurposing Django's native permission flags to represent "this person owns/administers things."

# Why not just have a role field set to "owner" instead?
# That's a real design question, not a rhetorical one — I'll come back to it in Design Discussion, because how this function is built reveals a specific (and slightly risky) architectural decision.

# 2. Imports

# Identical to restore_user and delete_user. Nothing new.

# 3. Signature
# python
# @transaction.atomic
# def promote_to_owner(*, user_id: str) -> User:

# Same shape as every function in this family now. You should be reading this cold.

# 4. Body — line by line
# python
# user = get_user(user_id=user_id)
# if not user:
#     raise ApplicationError("User Not Found.", code=ErrorCode.USER_NOT_FOUND)

# Same existence guard as delete_user/restore_user — good, consistent.

# But look closely at the message string: "User Not Found." — capital N, capital F. Every other file in this family used "User not found." — lowercase. This is a small but real inconsistency. If anything in the frontend displays this string directly to users, or if any test asserts on the exact message text, this mismatch will bite someone. Not a functional bug (the code=ErrorCode.USER_NOT_FOUND is what matters for programmatic handling), but worth flagging as the kind of copy-paste drift that accumulates across a codebase.

# python
# if user.is_superuser:
#     raise ApplicationError("User is already owner", code=ErrorCode.VALIDATION_ERROR)

# New pattern, worth slowing down on. This isn't a "does this thing exist" check like the ones before — it's a state precondition check: "is the action I'm about to perform even meaningful right now?"

# Verb: raise.
# Condition: user.is_superuser — read directly: "if this user is already a superuser."
# Why check this at all? Without it, calling promote_to_owner twice on the same person would just silently succeed both times — wasteful, but not wrong, exactly. So why guard it?

# Think about it from the caller's side: if an admin clicks "Promote to Owner" on someone who already is one, that's almost always a sign of a stale UI, a double-click, or a mistake — and a clear error ("User is already owner") is far more useful feedback than silent success that leaves the admin unsure whether anything happened.

# Notice ErrorCode.VALIDATION_ERROR here, not USER_NOT_FOUND. This is a different category of error — not "the thing you asked for doesn't exist" but "the thing you asked for doesn't make sense given the current state." Distinguishing these error codes matters because whatever's consuming this API can map them to different HTTP status codes — USER_NOT_FOUND → 404, VALIDATION_ERROR → 400.

# python
# user.is_superuser = True
# user.is_staff = True
# user.save(update_fields=["is_superuser", "is_staff"])
# return user

# Same mechanical pattern as before: set fields, save only those fields, return the object.

# Why set both is_superuser and is_staff, not just is_superuser?
# In Django, is_staff controls access to the Django admin site itself; is_superuser controls "bypasses all permission checks." An owner needs both — access to admin tooling and unrestricted permissions. Setting only one and not the other would create a superuser who can't get into the admin panel, or a staff member with no elevated rights — a broken half-state, which is exactly why they're both set together in the same call.

# 5. Design Discussion — the real RBAC question here

# This is where I'd push back a little, in the spirit of "why was it designed this way, what are the trade-offs."

# is_superuser is a Django-wide flag — it's not scoped to a company. Every other function in this file family (delete_user, restore_user) checked or referenced user.company_id — ownership and permissions were tied to a specific company. This function makes someone a superuser with no company scoping at all.

# Why does that matter? In a genuine multi-tenant RBAC system, "owner" should almost certainly mean "owner of Company X," not "owner of literally everything in the entire application, across every tenant." If is_superuser is Django's global bypass-all-permissions flag, then promote_to_owner may be accidentally granting platform-wide admin rights to someone who should only have rights within their own company.

# What would the trade-offs of the alternatives look like?

# Current approach (is_superuser/is_staff flags): Simple, leverages Django's built-in admin/permission machinery for free. Downside: coarse — it's all-or-nothing, global, not tenant-scoped.
# Alternative — a proper role field or a CompanyMembership model with role="owner" scoped per company: More correct for true multi-tenant RBAC — someone could be an owner of Company A and a regular member of Company B. Downside: more code to write, you lose Django admin's free integration with is_staff/is_superuser.

# This isn't necessarily a bug — depending on this project's actual requirements (maybe it's not truly multi-tenant, maybe there's only ever one company per deployment), using Django's built-in flags might be perfectly intentional. But it's exactly the kind of thing worth confirming rather than assuming, since "owner" reusing a global superuser flag is a common real-world RBAC mistake in projects that started single-tenant and grew multi-tenant later without this function being revisited.

# 6. Common Beginner Mistakes

# ❌ Inconsistent error message casing/wording across near-identical functions (the "User Not Found." vs "User not found." drift) — small, but it's exactly the kind of thing that makes a codebase feel unpolished and can break tests that check exact strings.

# ❌ Setting is_superuser = True without also setting is_staff = True (or vice versa) — leaves the user in a state that doesn't match the intent ("owner" should mean both admin-panel access and full permissions).

# ❌ Not distinguishing error codes by category (existence vs. validation) — lumping everything under one generic error code makes it impossible for the frontend to react differently (404 page vs. inline form warning).

# ❌ The scoping issue above — reusing a global permission flag to represent what should be a per-company role, silently over-granting access.

# 7. Pattern Recognition — updating your template

# Your mental template from restore_user now needs one more slot:

# python
# @transaction.atomic
# def <verb>_user(*, user_id: str) -> User:
#     user = get_user(user_id=user_id)
#     if not user:
#         raise ApplicationError("User not found.", code=ErrorCode.USER_NOT_FOUND)

#     [state precondition check — is this action valid right now?]  ← new
#     [domain-specific guard, e.g. assert_not_last_owner]

#     user.<field_a> = <new_value>
#     user.save(update_fields=[...])
#     return user

# The "is this action valid right now" check is a distinct concept from "does this even exist" — worth keeping as a separate mental slot, because it's the difference between a 404 and a 400 in how you'd eventually wire this into an API.

# 8. Real Project Usage

# Called from an admin action gated behind — ironically — an existing owner's permission check (only current owners should be able to promote someone else to owner; you'd want that enforced in the view or via a decorator before this function is ever reached).

# Given what just came up — is_superuser being global rather than company-scoped — do you want to check whether there's a demote_owner counterpart (which would tell us if this project treats ownership symmetrically), or move straight into wherever the actual permission-checking code lives (the decorators/middleware that gate access to endpoints like this one)? That'll tell us definitively whether ownership here is meant to be global or per-company.