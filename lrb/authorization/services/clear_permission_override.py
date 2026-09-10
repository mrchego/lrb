from django.db import transaction

from lrb.authorization.models.user_role import UserPermissionOverride
from lrb.authorization.selectors.get_user_permissions import invalidate_user_permissions_cache


@transaction.atomic
def clear_permission_override(*, user_id:str, permission_codename:str) -> bool:
    UserPermissionOverride.objects.filter(user_id=user_id, permission__codename=permission_codename).delete()
    invalidate_user_permissions_cache(user_id=user_id)
    return True

# Teaching: clear_permission_override

# This is the simplest write service you've seen — but it's simple on purpose, and the interesting thing is how it deliberately differs from remove_role, which looked almost identical in shape. Everything here is syntax you already know; the value is in the comparison.

# 1. What is it?

# A service that removes a permission override for a user — but unlike remove_role, it doesn't care whether one actually existed. It just makes sure, afterward, that no override remains.

# No new syntax at all here — every piece (@transaction.atomic, .filter(...).delete(), __ traversal, cache invalidation, -> bool) is something you've already learned. So this is a good moment to focus entirely on the design comparison with remove_role.

# 2. How is it written?

# UserPermissionOverride.objects.filter(user_id=user_id, permission__codename=permission_codename).delete()
# Same bulk-delete shape as remove_role. permission__codename is the same __ traversal you learned in list_roles (loading) and remove_role (filtering) — "follow the permission relationship, then check its codename field." Makes sense: UserPermissionOverride doesn't store the codename directly, only a link to a Permission object, so reaching through the relationship is how you filter by it.

# No unpacking of the return value
# This is the one real difference to notice syntactically. remove_role wrote:

# python
# deleted, _ = UserRole.objects.filter(...).delete()

# This function just writes:

# python
# UserPermissionOverride.objects.filter(...).delete()

# No assignment at all — the (count, breakdown) tuple .delete() returns is simply discarded. Nothing captures it, nothing checks it. This is a deliberate omission, not a mistake — see section 5.

# 3. Signature — broken into pieces
# python
# def clear_permission_override(*, user_id: str, permission_codename: str) -> bool:
# Piece	Meaning
# *,	keyword-only
# user_id: str	whose override to clear
# permission_codename: str	which permission's override to clear
# -> bool	fully typed, matching set_permission_override's complete signature

# No company_id here either — same gap you flagged in set_permission_override, worth tracing the same way.

# 4. Body — line by line
# python
# UserPermissionOverride.objects.filter(
#     user_id=user_id, permission__codename=permission_codename
# ).delete()

# Find any override matching this user and this permission's codename, and delete it — in one bulk operation, no fetch, no capturing the result.

# python
# invalidate_user_permissions_cache(user_id=user_id)
# return True

# Clear the cache (same pattern as every override/assignment change you've read), and always report success.

# 5. Why? — the real lesson in this file

# Why does remove_role check if not deleted: raise ..., but this function doesn't check anything at all?

# This is the key comparison, and it comes down to a genuine, meaningful difference in what each operation means:

# remove_role represents an explicit, intentional action: "remove this specific assignment." If nothing was there to remove, that's surprising and worth surfacing — it likely means the caller's assumption about the current state was wrong (maybe a stale UI, a double-submission, or a real bug), so raising ApplicationError is the honest, informative response.
# clear_permission_override represents a different kind of intent: "make sure there is no override for this permission" — i.e., "reset this permission back to whatever the user's role alone would grant." Whether an override existed before doesn't actually matter to the caller's goal; the end state they want ("no override exists") is achieved either way. Calling this on a permission that was never overridden isn't an error — it's simply a no-op that still successfully reaches the desired end state.

# This is the difference between an operation that should be idempotent (safe and harmless to call repeatedly, always resulting in the same end state, discussed more below) versus one that represents a specific, meaningful state transition where "nothing changed" genuinely signals something went wrong. Recognizing which kind of operation you're writing is a real design skill — not every delete needs a "did it actually delete something?" check; it depends on what the operation is supposed to mean to the caller.

# Why discard the (count, breakdown) tuple instead of capturing it like remove_role did?
# Directly following from the above: since the count isn't used for anything (no check depends on it), there's no reason to capture it — nothing to unpack, nothing to name, nothing to ignore with _. This is a small but good habit: don't capture a return value you have no use for, just because a sibling function happened to.

# 6. Connections

# What comes in: user_id, permission_codename — no company scoping (same open question as set_permission_override).
# What goes out: always True — this function cannot fail in the normal sense; there's no error path at all in its own body.
# Where this fits: the "reset to default" counterpart to set_permission_override — likely a "remove override" button next to whatever UI lets an admin grant/revoke individual permissions, letting them return a user to "just use their role's normal permissions" for one specific permission.

# 7. Advanced concepts

# A) Idempotency — a concept worth naming explicitly
# An operation is idempotent if calling it once has the same effect as calling it many times in a row — the end state is what matters, not how many times you asked for it. "Delete this override if it exists" is a classic idempotent operation: calling it once when an override exists removes it; calling it again when there's now nothing left to remove still results in the exact same end state (no override), with no error. Compare this to assign_role, which is not idempotent in the same way — calling it twice with the same arguments triggers the IntegrityError/ALREADY_ASSIGNED path the second time, because "assign" represents a specific transition ("create a new link") that genuinely can't happen twice. Recognizing whether an operation is naturally idempotent helps you decide, as a designer, whether "nothing happened" should be an error or a quiet success.

# B) When not to check a delete count
# Following directly from idempotency: only bother capturing and checking .delete()'s return count when "zero rows deleted" is itself meaningful information the caller needs. If the operation's whole point is "ensure this doesn't exist" rather than "remove this specific known thing," checking the count would just be unnecessary code that occasionally raises an unhelpful error for what is, from the caller's perspective, a completely successful outcome.

# 8. Small example
# python
# overrides = {("u1", "orders.delete"): True}

# def clear_permission_override(*, user_id, permission_codename):
#     overrides.pop((user_id, permission_codename), None)   # .pop with default -> never raises
#     return True

# clear_permission_override(user_id="u1", permission_codename="orders.delete")  # removes it
# clear_permission_override(user_id="u1", permission_codename="orders.delete")  # already gone — still True, no error

# (dict.pop(key, None) here mirrors the same idempotent spirit — "remove if present, don't complain if not.")

# 9. What you should remember
# Not every delete needs a "did something actually get deleted?" check — that check belongs on operations where "nothing happened" is itself meaningful and unexpected (remove_role); it's unnecessary noise on operations meant to be idempotent "ensure this state" calls (clear_permission_override).
# Idempotent operations ("make sure X is true/gone") should generally succeed quietly even when there was nothing to do — this is a deliberate design choice, not laziness, and it makes the function safer to call repeatedly (e.g., from a retry, or a UI that doesn't track state precisely).
# Don't capture a return value you have no use for — if nothing downstream checks the count, there's no need to unpack .delete()'s tuple at all, unlike remove_role, where the count was load-bearing.
# When two functions look almost syntactically identical (remove_role vs. clear_permission_override), the interesting differences are usually in what they choose to check, not in new syntax — this is a higher-level reading skill: comparing intent and design choices between similar-looking functions, not just spotting new keywords.
# The missing company_id scoping gap here matches set_permission_override's — the same open question applies: confirm the calling resolver enforces company ownership before reaching this service, since this function itself provides no such protection.