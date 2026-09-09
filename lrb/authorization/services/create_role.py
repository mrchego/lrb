from __future__ import annotations
from django.db import transaction, IntegrityError
from lrb.authorization.models.permission import Permission
from lrb.authorization.models.role import Role
from lrb.core.exceptions import (
    AppValidationError,
    BusinessRuleViolationError,
    ErrorCode,
)


@transaction.atomic
def create_role(*, company, name, permission_codenames=None, is_default=False) -> Role:
    name = name.strip()
    if len(name) < 2:
        raise AppValidationError(
            message="Role name must be at least 2 characters long.", field="name"
        )
    permission_codenames = permission_codenames or []
    permissions = list(Permission.objects.filter(codename__in=permission_codenames))
    unknown = set(permission_codenames) - {p.codename for p in permissions}
    if unknown:
        raise AppValidationError(
            message=f"Unknown permission codename(s): {sorted(unknown)}",
            field="permission_codenames",
        )
    try:
        role = Role.objects.create(company=company, name=name, is_default=is_default)
        if permissions:
            role.permissions.set(permissions)
        return role
    except IntegrityError:
        raise BusinessRuleViolationError(
            message="A role with this name already exists for this company.",
            code=ErrorCode.BUSINESS_RULE,
        )


# Teaching: create_role

# This is your first service function so far (everything before was a selector — read-only). Services are where writes, validation, and business rules live, and this one shows almost every core pattern your project uses: @transaction.atomic, custom validation exceptions, set operations, and catching a database-level error to turn it into a business-level one. Let's go through it fully.

# 1. What is it?

# A function that creates a new Role for a company — validating the name, resolving permission codenames into real Permission objects, attaching them, and translating low-level database errors into meaningful, structured application errors.

# New pieces:

# from django.db import transaction, IntegrityError
# @transaction.atomic — a decorator
# AppValidationError, BusinessRuleViolationError, ErrorCode — custom exception types
# name.strip() — a string method
# permission_codenames or [] — the or operator used for a default fallback
# Permission.objects.filter(codename__in=permission_codenames) — __in lookup
# set(...), {...} set literal, and - (set difference)
# list(...) — converting a queryset to a list
# Role.objects.create(...)
# role.permissions.set(permissions)
# try/except IntegrityError:
# 2. How is it written?

# @transaction.atomic
# A decorator (you know these from @strawberry.mutation/@require_owner()) that wraps this whole function in a database transaction. Everything: creating the Role, and attaching its permissions, either all succeeds together, or if anything fails partway through, everything gets rolled back as if none of it happened. No decorator "arguments" here (no ()), because — unlike require_owner() — this decorator doesn't need any configuration; it's used directly.

# Why does this matter for this specific function? Look at the body: it creates a Role first, then separately calls .set(permissions) to attach permissions. Those are two separate database operations. Without @transaction.atomic, if the role got created successfully but then something failed while attaching permissions, you'd be left with a half-created role — one that exists but has none of the permissions it was supposed to have. @transaction.atomic guarantees that can't happen: either both steps commit together, or neither does.

# name.strip()
# .strip() is a built-in string method that removes leading/trailing whitespace. "  Manager  ".strip() becomes "Manager". This line reassigns name to its trimmed version — a normalization step, done before validation, so that a name like "  " (just spaces) doesn't sneak past a length check by looking non-empty.

# if len(name) < 2:
# len(...) — a built-in function that returns the number of characters in a string. Straightforward length validation.

# raise AppValidationError(message="...", field="name")
# Calling this custom exception class like a function, passing keyword arguments to build it — message (human-readable text) and field (which specific input field this error is about, so a frontend form could highlight exactly that field, not the whole form). This is a much richer, structured version of raise SomeError("text") — it carries machine-readable metadata, not just a string.

# permission_codenames = permission_codenames or []
# This is the or-as-default-fallback pattern. Remember: or in Python returns whichever side is "truthy" — and if the first side is falsy, it evaluates and returns the second side instead. Here:

# If permission_codenames is None (its default from the signature) or an empty list [] (also falsy), the expression evaluates to [].
# If it's a real, non-empty list, the expression evaluates to that same list, unchanged.

# So this line's real job: "make sure permission_codenames is always an actual list from this point forward, never None" — because the next lines are about to do list/set operations on it that would crash on None.

# Permission.objects.filter(codename__in=permission_codenames)
# New lookup type: __in. This means "match rows where this field's value is any one of the values in this list" — the SQL equivalent of WHERE codename IN ('orders.delete', 'staff.invite', ...). One query fetches every Permission whose codename appears anywhere in the input list, instead of looping and querying once per codename.

# list(Permission.objects.filter(...))
# Wrapping a queryset in list(...) forces it to execute right now and become a real Python list, rather than staying lazy. This matters here because the code is about to use this result twice below (once to check for unknowns, once — implicitly, via the permissions variable — to attach to the role). If you didn't force it into a list, each use of the lazy queryset could silently re-run the query against the database again — wasteful, and in rare cases, could even return inconsistent results if the data changed between the two uses. Forcing it into a list "locks in" one snapshot of the result to reuse safely.

# {p.codename for p in permissions}
# A set comprehension — same shape as the dict comprehension you learned earlier, but building a set (curly braces, no key:value, just values) instead of a dict. A set is like a list, but with no duplicates and no order — ideal here because we only care about "which codenames did we successfully find," not how many times or in what order.

# set(permission_codenames) - {p.codename for p in permissions}
# - between two sets means set difference: "everything in the left set that is not in the right set." So this line computes: "which codenames did the caller ask for, that we did not find a matching Permission for?" — i.e., typos or invalid codenames. This is a clean, single-expression way to answer "what's missing" without writing a manual loop with an if x not in y check.

# f"Unknown permission codename(s): {sorted(unknown)}"
# An f-string (formatted string) — the f before the quotes means "evaluate the {...} parts as real Python expressions and insert their result into the string." sorted(unknown) turns the (unordered) set into a sorted list, so the error message is stable and readable rather than showing set items in arbitrary order every time.

# Role.objects.create(company=company, name=name, is_default=is_default)
# .create(...) is a Django manager method that does two things in one call: builds a new model instance with these field values, and immediately saves it to the database, returning the saved object. (Contrast this with Role(company=company, ...) alone, which would only build the object in memory without saving — .create() is the "build and save in one step" shortcut.)

# role.permissions.set(permissions)
# role.permissions — access to the many-to-many relationship from this specific role to its permissions (you saw this relationship's reverse direction, permissions, back in list_roles's prefetch_related("permissions")). .set(permissions) replaces whatever's currently linked with exactly the list you give it — the standard way to assign a many-to-many relationship's full contents in one call, rather than adding items one at a time in a loop.

# try / except IntegrityError:
# IntegrityError is a Django/database-level exception — it's raised when a database constraint is violated (e.g., a unique constraint saying "role names must be unique per company," enforced at the database schema level, not in Python code). This function doesn't manually check "does a role with this name already exist?" beforehand — it just tries to create it, and if the database itself rejects the insert due to a uniqueness rule, Python catches that low-level failure here.

# 3. Signature — broken into pieces
# python
# def create_role(*, company, name, permission_codenames=None, is_default=False):
# Piece	Meaning
# *,	every parameter below must be passed by keyword
# company	required, no default, no type hint
# name	required, no default, no type hint
# permission_codenames=None	optional, defaults to None — no type hint
# is_default=False	optional, defaults to False — no type hint
# no ->	no return type hint

# This is worth stopping on directly: none of the four parameters have type hints, and there's no return type hint either. Your project convention explicitly calls for type hints on service functions. This is real, meaningful drift — much more significant than the missing return hints you spotted on the read-side selectors, because here it's the entire signature, not just the return type. A properly-typed version would look like:

# python
# def create_role(
#     *,
#     company: Company,
#     name: str,
#     permission_codenames: Optional[list[str]] = None,
#     is_default: bool = False,
# ) -> Role:
# 4. Body — line by line
# python
# name = name.strip()
# if len(name) < 2:
#     raise AppValidationError(message="Role name must be at least 2 characters long.", field="name")

# Normalize the name, then reject it early if too short — fail fast, before touching the database at all.

# python
# permission_codenames = permission_codenames or []

# Guarantee a real list to work with, whether the caller passed None (the default) or actual codenames.

# python
# permissions = list(Permission.objects.filter(codename__in=permission_codenames))
# unknown = set(permission_codenames) - {p.codename for p in permissions}
# if unknown:
#     raise AppValidationError(message=f"Unknown permission codename(s): {sorted(unknown)}", field="permission_codenames")

# Look up all requested permissions in one query. Compute which requested codenames didn't match anything real. If any didn't match, reject the whole operation — don't silently create a role with only the valid subset of permissions; that would hide a caller's mistake (e.g., a typo'd codename) instead of surfacing it.

# python
# try:
#     role = Role.objects.create(company=company, name=name, is_default=is_default)
#     if permissions:
#         role.permissions.set(permissions)
#     return role
# except IntegrityError:
#     raise BusinessRuleViolationError(
#         message="A role with this name already exists for this company.",
#         code=ErrorCode.BUSINESS_RULE,
#     )

# Attempt the actual write: create the role row, then (only if there are any real permissions to attach — skip the extra query entirely if the list is empty) attach them. If everything succeeds, return the new Role. If the database rejects the insert because of a duplicate-name constraint, catch that low-level IntegrityError and re-raise it as a different, meaningful exception type — BusinessRuleViolationError — with a human-readable message and a machine-readable code.

# 5. Why?

# Why validate permission codenames manually (unknown = set(...) - {...}) instead of just letting a bad codename silently produce zero matching permissions?
# Because silently ignoring an invalid input is a worse failure mode than rejecting it clearly. If a caller typos "orders.delet" (missing an e), and the code just filtered to matching permissions and moved on, the role would be created successfully but silently missing a permission the caller thought they were granting — a dangerous, invisible bug (imagine this being a security-relevant permission that silently didn't get attached). Raising AppValidationError instead makes the mistake loud and immediate.

# Why catch IntegrityError instead of checking "does a role with this name exist" before creating?
# You could write:

# python
# if Role.objects.filter(company=company, name=name).exists():
#     raise BusinessRuleViolationError(...)
# role = Role.objects.create(...)

# But this has a subtle flaw: between the .exists() check and the .create() call, in a real concurrent system, another request could create a role with that exact name in between — a race condition. Relying on the database's own unique constraint and catching the resulting IntegrityError is more robust: the database itself is the single source of truth that enforces uniqueness atomically, and Python just translates whatever it says into a friendlier error. This is a real, subtle, important pattern: let the database enforce data integrity rules it's already good at, and catch the low-level failure to convert it into a domain-meaningful one — rather than re-implementing the same check yourself with a gap in the middle.

# Why re-raise as a different exception type (BusinessRuleViolationError) instead of just letting IntegrityError propagate?
# Because IntegrityError is a raw, Django/database-level concept — meaningless to a GraphQL frontend, and it would leak implementation details (SQL constraint names, etc.) if it reached the API boundary directly. Wrapping it in your project's own exception type keeps a clean boundary: everything above the service layer only ever needs to know about your project's own vocabulary of errors (AppValidationError, BusinessRuleViolationError, etc.), never raw database exceptions. This matches your format_application_error function you imported back in the mutations file — it's built to handle your exception types consistently.

# Why @transaction.atomic specifically here, matching your project's "all write services use it" convention?
# Because this function performs two separate writes (create the role, then set its permissions). Without atomicity, a crash between those two steps would leave inconsistent data behind. This is the textbook case atomic transactions exist for.

# 6. Connections

# What comes in: company (a Company object — the resolver would fetch this itself, likely from current.company_id after the gatekeeper check), name, an optional list of permission codename strings, and an is_default flag.
# What goes out: the newly created Role object, or one of two specific validation/business-rule exceptions.
# Where this fits: called from a mutation resolver (like the UserMutation class you read earlier, but presumably a sibling RoleMutation class) — wrapped in that resolver's own try/except ApplicationError block, which catches both AppValidationError and BusinessRuleViolationError (since both likely inherit from a common ApplicationError base, matching the import pattern you saw in the mutations file) and turns them into a success=False payload.
# Uses your selectors: doesn't call get_permission directly, but does the same kind of lookup (Permission.objects.filter(codename__in=...)) inline — worth noting this service reaches into the Permission model directly rather than composing existing selectors, which is a minor architectural choice you could question: should it have called something like a list_permissions_by_codenames selector instead of writing its own .filter()? Not wrong, just worth noticing as you build intuition for when services should reuse selectors versus query directly.

# 7. Advanced concepts

# A) Set operations as a validation technique
# set(a) - set(b) — "what's in A that's not in B" — is a genuinely useful, recognizable pattern any time you need to answer "which of these requested things don't exist / weren't matched." It's cleaner and faster than writing a manual loop with if item not in matched_list.

# B) Database constraints as the actual source of truth for uniqueness
# This is worth sitting with: your Role model almost certainly has something like unique_together = ("company", "name") (or a similar UniqueConstraint) defined at the database level. This function doesn't re-implement that rule in Python — it delegates enforcement to the database, and only translates the resulting failure into a nicer exception. A general lesson: don't duplicate a rule the database already enforces reliably; catch its failure instead.

# C) @transaction.atomic and exceptions together
# An important, subtle detail: when IntegrityError is raised inside the try block, Django's transaction machinery notices the transaction failed and marks it for rollback automatically — the partially-created Role (if it got that far) will not actually persist once the transaction rolls back, even though you raise a different exception (BusinessRuleViolationError) afterward. The atomic decorator and the try/except work together here: the except clause is about giving the caller a meaningful error message; the rollback itself is handled separately and automatically by @transaction.atomic.

# 8. Small example
# python
# class ValidationError(Exception): pass
# class BusinessRuleError(Exception): pass

# existing_names = {"Manager", "Viewer"}

# def create_role(*, name, permission_codenames=None):
#     name = name.strip()
#     if len(name) < 2:
#         raise ValidationError("Name too short.")
#     permission_codenames = permission_codenames or []
#     known = {"orders.delete", "staff.invite"}
#     unknown = set(permission_codenames) - known
#     if unknown:
#         raise ValidationError(f"Unknown: {sorted(unknown)}")
#     if name in existing_names:
#         raise BusinessRuleError("Role name already exists.")
#     existing_names.add(name)
#     return {"name": name, "permissions": permission_codenames}

# print(create_role(name="  Editor  ", permission_codenames=["orders.delete"]))
# # {'name': 'Editor', 'permissions': ['orders.delete']}
# 9. What you should remember
# @transaction.atomic belongs on any service that performs more than one related database write — it guarantees "all or nothing," preventing half-finished, inconsistent data if something fails partway through.
# x or default is a quick, idiomatic way to normalize None/empty inputs into a safe default — recognize it whenever you see a parameter used in list/set operations right after being assigned this way.
# set(a) - set(b) answers "what's requested but not found/matched" — a clean validation pattern worth reusing whenever you need to check a list of inputs against a list of valid known values.
# Prefer catching a database-level exception (IntegrityError) over a manual "check then create" — when a constraint already exists at the database level. Checking first and creating second leaves a race-condition gap; letting the database enforce its own rule and translating the failure is safer.
# A completely unhinted signature (no parameter or return type hints) on a service function is a real, notable inconsistency to flag — your project's convention explicitly calls for typed service functions, and this one skips it entirely. Worth raising as a concrete fix when you're ready to practice writing/reviewing real code, not just reading it.