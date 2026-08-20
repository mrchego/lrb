from __future__ import annotations
from typing import Optional
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError
from lrb.accounts.selectors.get_user import get_user
from lrb.company.models.company import Company
from lrb.core.exceptions import (
    AppValidationError,
    ApplicationError,
    BusinessRuleViolationError,
    ErrorCode,
)
from lrb.core.validators.email import validate_email
from lrb.core.validators.phone import validate_phone_number
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lrb.accounts.models import User


@transaction.atomic
def update_user(
    *,
    user_id: str,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    phone: Optional[str] = None,
    avatar=None,
    company: Optional[Company] = None,
    email: Optional[str] = None,
) -> User:
    user = get_user(user_id=user_id)
    if user is None:
        raise ApplicationError("User not found.", code=ErrorCode.USER_NOT_FOUND)

    if first_name is not None:
        user.first_name = first_name
    if last_name is not None:
        user.last_name = last_name
    if phone is not None:
        validate_phone_number(phone)
        user.phone = phone
    if company is not None:
        user.company = company
    if avatar is not None:
        user.avatar = avatar
    if email is not None:
        validate_email(email)
        user.email = email

    try:
        user.full_clean()
        user.save()
        return user
    except ValidationError as e:
        if "email" in e.message_dict:
            raise BusinessRuleViolationError(code=ErrorCode.USER_ALREADY_EXISTS)
        field = list(e.message_dict.keys())[0]
        message = e.message_dict[field][0]
        raise AppValidationError(message, field=field)
    except IntegrityError:
        raise BusinessRuleViolationError(code=ErrorCode.USER_ALREADY_EXISTS)


# update_user — Full Walkthrough

# Good file to see next — this is your first update (as opposed to create) service, and it reuses several patterns you already know, but also introduces genuinely new ones (partial updates, a selector import). One thing worth flagging up front, though it turns out not to be an actual bug once we dig into it — I'll explain why in Section 2.

# 1. Purpose — Why this exists

# What problem is this solving?
# Editing a user is a different shape of problem than creating one. A caller might want to change just the phone number, or just the email, or several fields at once — but never all of them, and never fields that don't apply here at all (notice: no password, no can_login, no is_staff — those clearly live in their own dedicated services). This function needs to: find the existing user, apply only the fields the caller actually wants to change, validate the new state, and save — all while translating errors the same way create_user does.

# Why not just write user.first_name = x; user.save() wherever an edit is needed?
# Because that would skip validation (email/phone format checks, full_clean()), skip the duplicate-email safety net, and duplicate the same lookup-and-error-translation logic in every place a user might need editing.

# When is this used?
# A "edit profile" or "edit user" GraphQL mutation — a staff member updating someone's name, phone, email, company, or avatar, without touching security-sensitive fields like password or role flags.

# What breaks without it?
# Direct field edits scattered across the codebase, each one potentially forgetting validation, or forgetting that changing an email needs the same duplicate-detection safety net as creating one.

# 2. Imports — explained like you've never programmed
# python
# from typing import Optional
# from django.db import IntegrityError, transaction
# from django.forms import ValidationError
# from lrb.accounts.models import User
# from lrb.accounts.selectors import get_user
# from lrb.company.models.company import Company
# from lrb.core.exceptions import (
#     AppValidationError,
#     ApplicationError,
#     BusinessRuleViolationError,
#     ErrorCode,
# )
# from lrb.core.validators.email import validate_email
# from lrb.core.validators.phone import validate_phone_number

# Most of these you've already seen in create_user. Two are new.

# from django.forms import ValidationError — worth investigating rather than assuming it's wrong.
# At first glance this looks like the same bug pattern as the pytest_django.asserts mistake a few files back — importing something from a module that doesn't actually own it. But checking against how Django is actually built: django.forms.ValidationError isn't a different class that happens to share a name — Django's forms package re-exports the exact same ValidationError class object from django.core.exceptions. So except ValidationError here will still correctly catch the ValidationError that full_clean() raises (which comes from django.core.exceptions), because it's literally the same class either way you spell the import.

# That said — this is still worth changing, and here's the more precise reason why, rather than just "it's inconsistent with create_user": this file works entirely with a Django model (full_clean() is a model method, not a form method), and importing ValidationError from django.forms implies a connection to Django's forms system that doesn't exist anywhere else in this file. create_user correctly imports it from django.core.exceptions — the canonical home for this exception, independent of forms or models. Matching that import here isn't fixing a runtime bug; it's removing a misleading signal about where this exception actually comes from.

# from lrb.accounts.selectors import get_user
# This is new, and it's a meaningful signal: your project's convention (per your project notes) is strict separation between selectors (read-only queries — get_user, get_users_by_ids, list_users) and services (functions with side effects, wrapped in @transaction.atomic — create_user, update_user). This import is exactly that separation in action: update_user is a service, and instead of writing its own User.objects.filter(pk=...).first() inline, it reuses the selector you already reviewed a few turns ago. This is the direct payoff of having built get_user as its own function — it's now being composed into something bigger, unchanged.

# ApplicationError
# A new exception type alongside AppValidationError and BusinessRuleViolationError — presumably a more general-purpose error for "this thing you asked for doesn't exist," distinct from a validation failure (bad input shape) or a business rule violation (an action that's technically valid input but not allowed, like a duplicate email).

# 3. Signature — every symbol explained
# python
# @transaction.atomic
# def update_user(
#     *,
#     user_id: str,
#     first_name: Optional[str] = None,
#     last_name: Optional[str] = None,
#     phone: Optional[str] = None,
#     avatar=None,
#     company: Optional[Company] = None,
#     email: Optional[str] = None,
# ) -> User:

# Same @transaction.atomic decorator, same reasoning as create_user — this function does a read (via get_user) and, if validation passes, a write, and if anything fails partway through, nothing should be left half-applied.

# user_id: str — the one required parameter (no default) — you can't update a user without saying which one.

# Every other parameter is Optional[..., ] = None. This is the defining shape of this function, and it's worth naming explicitly as its own pattern: every field defaults to "don't touch this." None here doesn't mean "clear this field" — it means "the caller didn't mention this field, so leave it exactly as it is." That distinction matters enormously and we'll dig into it in Section 6, because it has a real consequence: this function cannot be used to intentionally clear a field back to blank (e.g., you can't use it to remove someone's phone number — passing phone=None just means "don't touch phone," not "erase phone").

# avatar=None — still untyped, same gap as in create_user. Worth the same fix: avatar: Optional[SomeImageType] = None.

# -> User — same confident promise as create_user: always returns a real User on success, always raises on failure, never returns None.

# Notice what's absent from this signature entirely: password, can_login, is_active, is_staff, is_superuser, is_founder. This is a deliberate design boundary, not an oversight — worth confirming, but almost certainly intentional: those fields likely have their own dedicated services (change_password, deactivate_user, promote_to_superuser) that carry their own permission checks and business rules, rather than being editable through this general-purpose "update basic profile info" function. Bundling security-sensitive flags into a general update function would make it much easier to accidentally grant is_superuser=True through a permission-check gap somewhere.

# 4. Classes

# No class defined here — same reasoning as before. But this file, like create_user, does use a class (User) — this time not to construct a new instance, but to mutate an existing one that get_user already fetched.

# 5. Body — line by line
# Fetch and guard
# python
# user = get_user(user_id=user_id)
# if user is None:
#     raise ApplicationError("User not found.", code=ErrorCode.USER_NOT_FOUND)

# get_user(user_id=user_id) — calling the selector you already reviewed, which returns Optional[User] — either the real user, or None.

# if user is None: raise ApplicationError(...) — this is the direct consequence of get_user's design choice to return None instead of raising. get_user stayed neutral ("here's a user, or nothing") specifically so that each caller could decide what "nothing" means for them. Here, in an update context, "nothing" is unambiguously an error — you can't update a user that doesn't exist — so this function is the one that turns that None into a raised exception, right at the point where it actually knows that's the correct response.

# The conditional field updates
# python
# if first_name is not None:
#     user.first_name = first_name
# if last_name is not None:
#     user.last_name = last_name
# if phone is not None:
#     validate_phone_number(phone)
#     user.phone = phone
# if company is not None:
#     user.company = company
# if avatar is not None:
#     user.avatar = avatar
# if email is not None:
#     validate_email(email)
#     user.email = email

# Six near-identical blocks, so let's read the shape once and note what varies.

# The pattern: if <param> is not None: — then, inside, an assignment: user.<field> = <param>. This is directly setting an attribute on the already-fetched, already-in-memory user object — no separate "update" method, just plain attribute assignment, exactly the same mechanism as when first_name=first_name was passed into User(...)'s constructor in create_user. The difference here is we're setting attributes on an existing object one at a time, rather than all at once in a constructor call.

# Why is not None and not just a truthy check, for every single one of these — even first_name, a string?
# Because an empty string is potentially a meaningfully different signal than "don't touch this" — though in practice, full_clean() would likely reject an empty first_name anyway if the model field disallows blank values. The consistent use of is not None throughout (rather than a plain truthy check, which was fine for things like company_id in list_users) reflects a project-wide habit here: for a function whose entire mechanism depends on distinguishing "not provided" from "provided," being explicit about None specifically, everywhere, keeps that mechanism unambiguous and consistent to read.

# What's different between phone/email and the other four: phone and email each run their format validator inside the same if block, immediately before the assignment — validate_phone_number(phone) then user.phone = phone; validate_email(email) then user.email = email. first_name, last_name, company, avatar have no such validator call — they're assigned directly, trusting full_clean() (later) to catch any structural problems.

# Save, with the exact same exception translation as create_user
# python
# try:
#     user.full_clean()
#     user.save()
#     return user
# except ValidationError as e:
#     if "email" in e.message_dict:
#         raise BusinessRuleViolationError(code=ErrorCode.USER_ALREADY_EXISTS)
#     field = list(e.message_dict.keys())[0]
#     message = e.message_dict[field][0]
#     raise AppValidationError(message, field=field)
# except IntegrityError:
#     raise BusinessRuleViolationError(code=ErrorCode.USER_ALREADY_EXISTS)

# This block is line-for-line identical in logic to what you already walked through in create_user — same reasoning applies without change: full_clean() before save(), message_dict[field][0] (not .message) to safely extract the error text, and IntegrityError as the race-condition backstop for the email-uniqueness case.

# 6. Beginner questions, answered proactively

# Why validate phone/email inline, right next to their assignment, instead of validating everything up front the way create_user does (all validators run before the User(...) constructor)?
# This is a real, worthwhile difference to notice rather than assume is arbitrary. In create_user, every field is always present (they're either required, or explicitly given a default), so validating everything up front before constructing the object makes sense — there's nothing conditional about it. Here, validation only makes sense if the field is actually being changed — there's no reason to validate a phone number that isn't being touched. Putting the validator call inside the same if block as the assignment keeps "should I check this" and "am I changing this" tied to the exact same condition, so they can't drift out of sync.

# Can I use this function to remove someone's phone number entirely — pass phone=None?
# No — and this is the single most important thing to understand about this function's design. phone=None here means "the caller didn't mention phone," triggering the if phone is not None: block to be skipped entirely, leaving whatever phone number the user already had, completely untouched. This function has no way to distinguish "don't change this" from "clear this to blank" — both would require passing None, and None always means the former. If clearing a field is a real requirement, this function would need a different mechanism (a separate sentinel value, or a dedicated clear_phone service).

# Why does email get the exact same "check for duplicate" branch (if "email" in e.message_dict) as create_user, even though we're updating an existing user, not creating one?
# Because uniqueness constraints don't care whether the row is new or existing — if you update User A's email to match User B's already-existing email, that's still a duplicate, and full_clean()'s uniqueness check (and the database's UNIQUE constraint, as a backstop) will catch it exactly the same way it would during creation.

# 7. Design discussion

# Why not use **kwargs or a dict of fields-to-update, instead of six explicit optional parameters?
# Explicit parameters are self-documenting and type-checkable — exactly the same trade-off discussed for list_users's filters. A caller (and their IDE) can see precisely which fields are editable through this function, and a typo'd field name would be caught immediately as a TypeError: unexpected keyword argument, rather than silently doing nothing (which is what a **kwargs-based dynamic-setattr approach could easily hide).

# Trade-off worth naming, similar to list_users: if this function eventually needs to support many more editable fields, six-plus near-identical if x is not None: user.x = x blocks becomes repetitive. A more scalable version might loop over a small mapping of {param_name: value} pairs — but that trades away the current version's explicitness and type-checkability, so it's a real trade-off, not a strict improvement.

# Why exclude security-sensitive fields (password, is_staff, etc.) from this function rather than just trusting the resolver's permission check to gate them?
# Keeping them out of the function signature entirely is a stronger guarantee than a permission check alone — a permission check can have bugs or be forgotten on one particular mutation; a field that simply doesn't exist on this function's signature can never be set through it, no matter what a resolver does or forgets to do. This is defense-in-depth: even if a future resolver accidentally exposed update_user to the wrong permission level, it still couldn't be used to grant superuser access.

# 8. DIY Recipe — build one like this yourself

# How to build your own "partial update" service:

# Fetch the existing object via a selector first, and immediately guard against None — turn "not found" into a raised exception here, since an update on a nonexistent record is always an error, unlike a lookup that might legitimately find nothing.
# Make every updatable field Optional[...] = None, and treat None consistently as "don't touch this field" — document that clearly, since it means this function structurally cannot clear a field to blank.
# For each field, use if param is not None: before assigning — never a plain truthy check, since you need to distinguish "not provided" from "provided but falsy" in exactly the same way regardless of the field's type.
# Run field-specific validators only inside the same conditional block as the assignment — don't validate fields that aren't being changed.
# Deliberately exclude security-sensitive fields from the signature entirely — don't rely on a permission check alone to protect fields that should never be casually editable.
# Reuse the exact same full_clean() → save() → exception-translation block from your create function — this logic doesn't need to differ between create and update.
# 9. General pattern recognition

# This is the "fetch, partially mutate, validate, save" pattern — the update-side sibling of create_user's "validate → construct → save" pattern:

# python
# @transaction.atomic
# def update_<thing>(*, <thing>_id: str, <optional fields> = None) -> Model:
#     obj = get_<thing>(<thing>_id=<thing>_id)
#     if obj is None:
#         raise ApplicationError(...)
#     if field is not None:
#         obj.field = field
#     # ...repeat per field...
#     try:
#         obj.full_clean()
#         obj.save()
#         return obj
#     except ValidationError as e:
#         # same translation as create
#     except IntegrityError:
#         # same translation as create

# You'll reuse this shape for update_company, update_role, or anything else that supports partial edits.

# 10. Real project usage
# python
# def resolve_update_user(self, info, user_id: str, first_name: str = None, phone: str = None) -> UserPayload:
#     actor = get_current_user(info)
#     require_permission(actor=actor, codename="staff.edit_users")
#     try:
#         user = update_user(user_id=user_id, first_name=first_name, phone=phone)
#     except AppValidationError as e:
#         return UserPayload(success=False, errors=[e.to_error_response()])
#     except (BusinessRuleViolationError, ApplicationError) as e:
#         return UserPayload(success=False, errors=[e.to_error_response()])
#     return UserPayload(success=True, user=user)
# 11. Common beginner mistakes

# ❌ Assuming phone=None clears the phone number — it doesn't; it means "leave it as-is." A genuinely common source of confusion in partial-update APIs.

# ❌ Using a plain truthy check (if phone:) instead of is not None — would incorrectly skip an intentional update to an empty string, if that were ever a valid state.

# ❌ Forgetting the user is None guard after get_user, then crashing later with AttributeError on user.first_name = ... when the ID doesn't correspond to a real row.

# ❌ Adding security-sensitive fields to a general update function "just this once" for convenience — undermines the defense-in-depth this function's signature currently provides.

# 12. Think like the original developer
# What problem am I solving? "I need to let callers change a subset of a user's basic profile fields, without needing to resend every field, and without touching anything security-sensitive."
# What inputs will I need? Which user (required), plus every editable field, each optional, each meaning 'don't touch this' when omitted.
# What could go wrong? The user ID doesn't exist; a new phone or email fails format validation; a new email collides with an existing user's email (common case, or a race condition).
# How should I report errors? Not-found becomes its own distinct error type (ApplicationError), separate from validation failures and duplicate-email business rule violations — three different problems, three different exception types.
# What should happen if everything works? Return the same, now-mutated User object — no need to re-fetch it, since it's already sitting in memory with the new values applied.
