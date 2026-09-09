from django.db import transaction
from lrb.authorization.models.role import Role
from lrb.core.exceptions import ApplicationError, ErrorCode


@transaction.atomic
def delete_role(*, role_id, company_id):
    role = Role.objects.filter(pk=role_id, company_id=company_id).first()
    if not role:
        raise ApplicationError(message="Role not found.", code=ErrorCode.ROLE_NOT_FOUND)
    if role.user_roles.exists():
        raise ApplicationError(
            message="Cannot delete a role that is still assigned to staff. Reassign them first.",
            code=ErrorCode.BUSINESS_RULE,
        )

    role.delete()
    return True


# Teaching: delete_role

# Short one — almost every piece here is something you've already learned (@transaction.atomic, the pk=/company_id lookup, the not-found pattern, raising ApplicationError). Two genuinely new things: .exists() and a business-rule guard that checks a relationship before allowing a delete. Let's go through it fully anyway, since the reasoning matters even where the syntax is familiar.

# 1. What is it?

# A service that deletes a role — but only if it's not currently assigned to any staff member. This is a guarded delete: instead of just removing the row, it first checks whether doing so would leave the system in a broken or confusing state.

# New piece: role.user_roles.exists().

# 2. How is it written?

# role = Role.objects.filter(pk=role_id, company_id=company_id).first()
# Identical to the lookup inside update_role — same scoped-by-company pattern you've now seen three times. By this point you should recognize this shape instantly: "fetch one row by primary key, but only if it also belongs to the right company; treat 'wrong company' the same as 'doesn't exist.'"

# if not role: raise ApplicationError(...)
# Same not-found guard as update_role.

# role.user_roles.exists()
# role.user_roles — this is the reverse relationship from Role back to whatever join/assignment model connects roles to users (you saw this exact name, user_roles, back in list_roles's prefetch_related("permissions", "user_roles__user") — that confirms this is the same relationship, just accessed here instead of pre-loaded).

# .exists() is a queryset method that returns a plain True/False: "does at least one row match, yes or no?" It's the correct tool here for a very specific reason — see section 5. It does not load any actual rows into Python; it asks the database "is there at least one match?" directly (translating to an efficient SQL query using EXISTS, if you're curious about the underlying SQL), which is faster than fetching all matching rows just to check if the list is non-empty.

# role.delete()
# A method every Django model instance has: delete this specific row from the database. Straightforward — no new concept here beyond what .save() and .create() already taught you (model instances carry methods that translate directly into database operations).

# return True
# Just a plain boolean, not a Role object like create_role/update_role returned. This tells you something about what the caller needs back: there's no "delete role but return the role" — once it's gone, there's nothing left to return, so a simple success signal (True) is all that's meaningful. Compare this to your SimpleMutationPayload(success=True) pattern from the mutations file — this True is probably exactly what feeds that success field.

# 3. Signature — broken into pieces
# python
# def delete_role(*, role_id, company_id):
# Piece	Meaning
# *,	both parameters keyword-only
# role_id	required — which role to delete
# company_id	required — security scope; no optional version here, unlike get_role, because a delete operation should never be allowed to skip tenant scoping
# no ->	no return type hint (should be -> bool, matching the pattern you've flagged in every write service so far)

# Worth noticing: unlike get_role, this function makes company_id mandatory, not optional. That's the right call — even if get_role might reasonably allow an unscoped lookup in some admin context, a destructive operation like delete should never have an escape hatch that skips the ownership check. Good instinct to compare this against get_role's looser signature and notice the difference is deliberate and appropriate.

# 4. Body — line by line
# python
# role = Role.objects.filter(pk=role_id, company_id=company_id).first()
# if not role:
#     raise ApplicationError(message="Role not found.", code=ErrorCode.ROLE_NOT_FOUND)

# Fetch and scope-check, exactly as before.

# python
# if role.user_roles.exists():
#     raise ApplicationError(
#         message="Cannot delete a role that is still assigned to staff. Reassign them first.",
#         code=ErrorCode.BUSINESS_RULE,
#     )

# Before deleting anything, check: is this role currently assigned to any user? If yes, refuse — with a message that tells the caller what to do about it ("reassign them first"), not just that it failed.

# python
# role.delete()
# return True

# If it passed both checks, actually remove the row, and signal success.

# 5. Why?

# Why check role.user_roles.exists() at all — why not just let the delete happen, or let the database handle it?
# This is a genuine, important design decision, and there are actually two different ways this could have been handled, worth comparing:

# Database-level protection: if the foreign key from UserRole to Role were set up with on_delete=models.PROTECT (or Django would simply raise an error on delete if on_delete=models.CASCADE wasn't set and rows still reference it), the database/ORM itself would refuse the delete and raise a low-level error — similar in spirit to how create_role let the database's unique constraint do the work and just caught IntegrityError.
# Explicit, application-level check (what this code actually does): manually check .exists() before attempting delete, and raise a clear, business-meaningful error with a helpful message, before ever touching the database's delete machinery.

# The code chose option 2 here, and the reason is almost certainly the quality of the error message. A raw database-level protection error would be cryptic and unhelpful to a frontend user ("IntegrityError: foreign key constraint violation" means nothing to someone using an admin panel). By checking explicitly first, the code can raise ApplicationError with a friendly, actionable message: "Cannot delete a role that is still assigned to staff. Reassign them first." This is a direct parallel to create_role's IntegrityError-catching — same underlying goal (translate a low-level failure into a meaningful business message) — but here, the check happens proactively, before attempting the operation, rather than reactively, by catching a failure after the fact. Both are valid strategies; which one fits depends on whether you can cheaply check the condition beforehand (.exists() is cheap) versus whether the failure is rare/hard to predict in advance (like a race-condition-prone uniqueness check, better handled reactively).

# Why .exists() instead of if role.user_roles.all(): or if len(role.user_roles.all()) > 0:?
# Both alternatives would work correctly, but wastefully — they'd fetch every single assigned user's full row just to answer a yes/no question. .exists() is specifically built for this: "just tell me if anything matches, don't bother sending me the actual data." Recognizing when you only need a boolean answer (versus needing the actual rows) is a real performance habit worth building — same spirit as choosing select_related/prefetch_related only when you actually need the related data.

# Why is @transaction.atomic on this function, when it looks like there's only one write (role.delete())?
# Good question to ask, since earlier you learned atomicity matters when there are multiple writes that need to succeed or fail together. Here, role.delete() might look like a single operation, but depending on the model relationships, a single .delete() call can cascade — if other models have on_delete=models.CASCADE pointing at Role, deleting a role could trigger deletions of related rows too, all as part of one logical operation. @transaction.atomic ensures that cascade, however many rows it touches, either fully completes or fully rolls back — consistent with your project's blanket rule ("@transaction.atomic on all write services") rather than something you'd need to reason about case-by-case every time.

# 6. Connections

# What comes in: role_id and company_id (the caller's own company, for scoping).
# What goes out: True on success, or an ApplicationError — either "not found" or "still in use."
# Where this fits: the delete-side counterpart to create_role/update_role/get_role, called from a RoleMutation resolver, almost certainly wrapped the same way as every mutation in your UserMutation file: try/except ApplicationError as e: return SimpleMutationPayload(success=False, errors=[format_application_error(e)]).
# Connects to user_roles: confirms the relationship structure hinted at back in list_roles and list_user_overrides — there's a UserRole (or similarly named) model linking users to roles, and it's referenced consistently across read (list_roles's prefetch), and now write (delete_role's guard) operations.

# 7. Advanced concepts

# A) Proactive check vs. reactive catch — same underlying goal, opposite timing
# This is worth holding up directly against create_role's IntegrityError handling, since it's the same underlying principle applied in reverse order:

# create_role: attempt the write, catch the failure, translate it.
# delete_role: check the condition first, avoid attempting the write at all if it would fail.
# Both protect the same goal — never let a low-level, uninformative database error reach the user — but the direction differs based on what's practical to check ahead of time versus what's only reliably knowable by trying (uniqueness races are hard to check safely in advance; "does anything reference this row" is cheap and safe to check in advance).

# B) .exists() short-circuits at the database level
# Under the hood, .exists() generates SQL using SELECT 1 ... LIMIT 1 (or an equivalent EXISTS clause) — the database itself stops looking the instant it finds one matching row, rather than counting or fetching everything. This is meaningfully faster than any approach that materializes the full list first, especially as data grows — a good habit to reach for whenever the only question you're asking is "is there at least one?"

# 8. Small example
# python
# class NotFoundError(Exception): pass
# class BusinessRuleError(Exception): pass

# roles = {"1": {"company": "A", "assigned_users": []}}
# user_roles = {"1": ["userX"]}   # role "1" is assigned to a user

# def delete_role(*, role_id, company_id):
#     role = roles.get(role_id)
#     if not role or role["company"] != company_id:
#         raise NotFoundError("Role not found.")
#     if user_roles.get(role_id):
#         raise BusinessRuleError("Still assigned to staff.")
#     del roles[role_id]
#     return True

# delete_role(role_id="1", company_id="A")
# # raises BusinessRuleError — role "1" is still assigned
# 9. What you should remember
# .exists() is the right tool whenever you only need a yes/no answer about whether related rows are present — it's cheaper than fetching or counting the actual rows, and it directly expresses your intent ("is there anything?") rather than implying you care about the data itself.
# A guarded delete (check a business condition before deleting) protects against leaving other data in a broken/dangling state — here, deleting a role that's still assigned would leave staff members pointing at a role that no longer exists (or trigger an unwanted cascade delete of their assignments).
# The same underlying goal — never let a raw database error reach the user — can be achieved either proactively (check first) or reactively (catch the failure) — which one to use depends on whether the condition is cheap and safe to check ahead of time.
# @transaction.atomic still matters even for what looks like "just one line" (role.delete()), because a single delete call can cascade into multiple underlying database operations depending on model relationships — better to apply it as a blanket rule on all write services (as your project does) than to judge it case by case.
# A required, non-optional company_id on a destructive operation is a deliberate, correct security tightening — compare this against get_role's optional company_id and notice that the stakes of the operation (read vs. permanent delete) justify removing any flexibility that could allow skipping the ownership check.