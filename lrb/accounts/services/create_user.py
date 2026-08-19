from typing import Optional

from django.db import transaction, IntegrityError
from django.core.exceptions import ValidationError
from lrb.accounts.models import User
from lrb.company.models.company import Company
from lrb.core.validators.password import validate_password_strength
from lrb.core.exceptions import (
    AppValidationError,
    BusinessRuleViolationError,
    ErrorCode,
)
from lrb.core.validators.email import validate_email
from lrb.core.validators.phone import validate_phone_number


@transaction.atomic
def create_user(
    *,
    email: str,
    first_name:str,
    last_name:str,
    password: Optional[str] = None,
    phone: Optional[str] = None,
    avatar=None,
    company: Optional[Company] = None,
    can_login: bool = True,
    is_active: bool =True,
    is_staff: bool =False,
    is_superuser: bool =False,
    is_founder: bool =False,
)-> User:
    validate_email(email)
    if phone:
        validate_phone_number(phone)

    if password is not None:
        try:
            validate_password_strength(password)
        except ValidationError as e:
            message = e.messages[0] if hasattr(e, "messages") else e.message
            raise AppValidationError(message, field="password")

    user = User(
        email=email,
        first_name=first_name,
        last_name=last_name,
        phone=phone or "",
        avatar=avatar,
        company=company,
        can_login=can_login,
        is_active=is_active,
        is_staff=is_staff,
        is_superuser=is_superuser,
        is_founder=is_founder,
    )

    if password is not None:
        user.set_password(password)
    else:
        user.set_unusable_password()

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
    
    
    
    
# 1. Purpose — Why this exists

# What problem is this solving?
# Creating a user isn't just "insert a row." It needs: validating the email format, validating the phone format (if given), validating password strength (if a password is given — some users might be invited without one and set it later), setting the password hashed, handling the "no password" case safely, running Django's model-level validation, saving, and translating low-level errors (ValidationError, IntegrityError) into your application's own error vocabulary (AppValidationError, BusinessRuleViolationError) so callers (like GraphQL mutations) never have to know or care about Django/database internals.

# Why not just write User.objects.create(...) wherever a user needs to be made?
# Because that would skip every validation step above, skip password hashing (.create() would store a plaintext password if you passed one as a field), and leave every caller to duplicate the exact same error-translation logic. This function is the single trusted gate through which every new user must pass.

# When is this used in a real project?
# Signup flows, staff-invite flows (creating a user with can_login=True but password=None, to be set via an invite link later), admin-created accounts — any path in the app that results in a brand-new User row.

# What breaks without it?
# Users could be created with plaintext passwords, invalid emails, weak passwords, or duplicate emails slipping through as confusing raw database errors instead of clean, catchable application errors.

# 2. Imports — explained like you've never programmed
# python
# from typing import Optional

# from django.db import transaction, IntegrityError
# from django.core.exceptions import ValidationError
# from lrb.accounts.models import User
# from lrb.company.models.company import Company
# from lrb.core.validators.password import validate_password_strength
# from lrb.core.exceptions import (
#     AppValidationError,
#     BusinessRuleViolationError,
#     ErrorCode,
# )
# from lrb.core.validators.email import validate_email
# from lrb.core.validators.phone import validate_phone_number

# You already know Optional, User, and the dotted-path pattern for your own project's modules. Let's cover what's new:

# from django.db import transaction, IntegrityError — two separate things pulled from the same module in one line (you can list multiple names after import, separated by commas). transaction is Django's tool for grouping database operations so they either all succeed or all roll back together. IntegrityError is the exception Django's database layer raises when a database-level constraint is violated — most relevantly here, a UNIQUE constraint on the email column.

# from django.core.exceptions import ValidationError — Django's built-in exception type for "this data doesn't pass validation," used both by field validators and by full_clean().

# from lrb.core.exceptions import (AppValidationError, BusinessRuleViolationError, ErrorCode) — notice the parentheses spanning multiple lines. This is Python's way of writing a multi-line import without needing a line-continuation backslash — anything inside (...) can span lines, and Python just reads it as one logical statement. These three names are all your own project's custom exception types and an enum-like ErrorCode, living in lrb/core/exceptions.py — the application's own error vocabulary, distinct from Django's built-in ValidationError/IntegrityError.

# validate_password_strength, validate_email, validate_phone_number — three of your own project's validator functions, each imported from its own dedicated file (lrb/core/validators/password.py, email.py, phone.py). One file per validator is itself a small design signal: each validator is treated as an independently testable, independently importable unit.

# 3. Signature — every symbol explained
# python
# @transaction.atomic
# def create_user(
#     *,
#     email: str,
#     first_name: str,
#     last_name: str,
#     password: Optional[str] = None,
#     phone: Optional[str] = None,
#     avatar=None,
#     company: Optional[Company] = None,
#     can_login=True,
#     is_active=True,
#     is_staff=False,
#     is_superuser=False,
#     is_founder=False,
# ) -> User:

# @transaction.atomic — this line, starting with @, is a decorator. A decorator wraps a function with extra behavior without you having to write that behavior yourself inside the function body. Here, it means: "run everything inside create_user as one atomic database transaction — if any exception is raised anywhere inside this function, undo every database write that happened so far, as if none of it ran." This is exactly your project's stated convention (@transaction.atomic on writes), and it earns its place here specifically because this function does multiple things that touch the database indirectly (validation queries inside full_clean(), then the actual save()) — you don't want a half-created user left behind if something fails partway through.

# def create_user(*, ...) — the lone * again, forcing every argument to be passed by keyword. With twelve parameters here, this convention isn't just nice-to-have — it's close to essential; imagine trying to call this positionally and keeping track of which of twelve True/False/None values goes where.

# Required parameters (no default): email: str, first_name: str, last_name: str — the caller must always provide these three.

# Optional-with-None-default parameters: password: Optional[str] = None, phone: Optional[str] = None, company: Optional[Company] = None. Notice company: Optional[Company] — this is the first time you've seen a type hint referencing one of your own model classes (imported at the top) rather than a built-in type like str or int. It means "either an actual Company model instance, or None — a user might not belong to any company yet."

# Boolean flags with concrete defaults: can_login=True, is_active=True, is_staff=False, is_superuser=False, is_founder=False. Worth flagging directly: none of these five have type hints, unlike literally every other parameter in this function (and unlike the fully-typed booleans you saw in list_users, like is_active: Optional[bool] = None). This is an inconsistency — they should read can_login: bool = True, is_staff: bool = False, and so on. It won't break anything at runtime, but it breaks the otherwise-total type-hint discipline this function holds everywhere else, and it's the kind of gap a linter or a careful code reviewer should catch.

# avatar=None — also untyped. Presumably this accepts either a file/image object or None — worth a proper hint like avatar: Optional[SomeImageType] = None once you know what type it should actually be.

# ) -> User: — the return type hint: this function promises to give back an actual User object (the newly created one), not Optional[User]. That's a meaningful, confident promise — it implies that on any failure, this function is expected to raise, not return None. Confirming that promise is exactly what we'll check in Section 5.

# 4. Classes

# No class defined in this file — but this is the first function where a class (User) is actually instantiated inside the body, which is worth pausing on. user = User(...) on line — creates a new, in-memory User object. At that point, it is not yet saved to the database — it exists only as a Python object in memory until .save() is explicitly called later. This is a distinction worth locking in: constructing a model instance and persisting it to the database are two separate steps in Django, not one.

# 5. Body — line by line
# Validation block
# python
# validate_email(email)
# if phone:
#     validate_phone_number(phone)

# validate_email(email) — call your validator, passing the email in. Notice: the return value (if any) is discarded — the function is called purely for its side effect (raising an exception if the email is malformed). Worth flagging as an open question rather than a confirmed bug: does validate_email normalize the email (e.g., lowercase it) and return the normalized version? If so, that normalized value is being silently thrown away here, since user.email=email below uses the original, unmodified email parameter — meaning "Foo@Example.com" and "foo@example.com" could both be accepted as distinct accounts. Worth confirming against validate_email's actual implementation.

# if phone: validate_phone_number(phone) — the guard-check pattern you already recognize: only validate the phone if one was actually given (since phone is optional), using a plain truthy check (correct here — an empty string phone number never means anything).

# python
# if password is not None:
#     try:
#         validate_password_strength(password)
#     except ValidationError as e:
#         raise AppValidationError(e.message, field="password")

# if password is not None: — deliberately is not None, not just if password: — matching the careful pattern you learned in list_users. Though here it matters less (an empty-string password would also be falsy and arguably should fail validation either way), using is not None consistently is still the safer habit.

# try: / except ValidationError as e: — this is exception handling: "attempt this code; if a ValidationError specifically gets raised while running it, catch it here instead of letting it crash the whole function, and give it the name e so I can inspect it."

# 🚩 Bug #1 — raise AppValidationError(e.message, field="password").
# This assumes e.message exists on the caught ValidationError. It's a genuinely easy assumption to make, but Django's ValidationError only sets a .message attribute when it was constructed from a single plain string. If validate_password_strength follows the common pattern of running multiple checks (length, complexity, common-password checks, etc.) and raising with a list of messages — which is exactly how Django's own built-in validate_password behaves — then the resulting ValidationError has .messages (plural, a list) or .error_list, but no .message attribute at all. Accessing e.message in that case raises AttributeError: 'ValidationError' object has no attribute 'message' — which is not caught by except ValidationError, so it would propagate up and crash the request with a confusing, unrelated error instead of the intended clean AppValidationError("password too weak", field="password").

# Whether this is actually a live bug depends on how validate_password_strength raises its error — but the code as written is fragile regardless, because it silently assumes a specific internal shape of the exception rather than defensively handling either case.

# Safer version:

# python
# except ValidationError as e:
#     message = e.messages[0] if hasattr(e, "messages") else e.message
#     raise AppValidationError(message, field="password")
# Building the model instance
# python
# user = User(
#     email=email,
#     first_name=first_name,
#     last_name=last_name,
#     phone=phone or "",
#     avatar=avatar,
#     company=company,
#     can_login=can_login,
#     is_active=is_active,
#     is_staff=is_staff,
#     is_superuser=is_superuser,
#     is_founder=is_founder,
# )

# Right side: User(...) — calling the model class itself as if it were a function is how you construct a new instance in Python. Each field=value pair inside sets that field's initial value on the new (not-yet-saved) object. phone=phone or "" — the familiar pattern: if phone is None (or empty), store an empty string instead of None in the database field — presumably because the phone column doesn't allow nulls, only allows blank strings.

# Left side: user — the in-memory object, not yet in the database.

# python
# if password is not None:
#     user.set_password(password)
# else:
#     user.set_unusable_password()

# user.set_password(password) — this is a method Django's AbstractBaseUser gives every user model. Critically, it does not store the plaintext password — it runs it through a secure hashing algorithm and stores only the hash. This is why the constructor above didn't include password=password as a field — passing it there would have stored it as a plain, unhashed field value, which would be a severe security bug.

# user.set_unusable_password() — for the "no password given" branch (e.g., a staff-invited account before they've set their own password), this explicitly marks the account as having no valid password at all — meaning check_password() will always return False for any input — rather than leaving the password field blank or None, which could be ambiguous or, worse, exploitable if not handled carefully by the authentication backend.

# Saving, with error translation
# python
# try:
#     user.full_clean()
#     user.save()
#     return user
# except ValidationError as e:
#     if "email" in e.message_dict:
#         raise BusinessRuleViolationError(code=ErrorCode.USER_ALREADY_EXISTS)
#     raise AppValidationError(e.message[0], field=list(e.message_dict.keys())[0])
# except IntegrityError:
#     raise BusinessRuleViolationError(code=ErrorCode.USER_ALREADY_EXISTS)

# user.full_clean() — Django's model-level validation: runs every field's built-in validators (max length, choices, uniqueness checks via a query, etc.) and raises ValidationError if anything fails — before touching the database with a write.

# user.save() — only reached if full_clean() didn't raise. This is the actual INSERT into the database.

# return user — only reached if both of the above succeeded — the newly created, now-persisted user, fulfilling the -> User promise from the signature.

# except ValidationError as e: — catches validation failures from full_clean().

# if "email" in e.message_dict: — full_clean()'s ValidationError is always dict-shaped (field name → list of error messages), so .message_dict is the correct way to inspect it — this part is fine. This line checks specifically: "was one of the failing fields email?" If so, translate it into your specific USER_ALREADY_EXISTS business error — a reasonable inference, since the most common reason full_clean() would flag email specifically is a uniqueness constraint (assuming email has unique=True on the model).


# Line 1: field = list(e.message_dict.keys())[0]

# Per the reading algorithm — assignment means read the right side first, and nested calls mean read inside-out. This line has both, nested three layers deep. Let's peel it from the innermost outward.

# e
# This is the ValidationError object we caught earlier in except ValidationError as e:. Think of it as a box that Django handed us when full_clean() failed — it contains information about which fields failed and why.

# .message_dict
# The dot means "reach inside e and grab this attribute." message_dict is a property Django's ValidationError provides specifically for errors that were built from multiple fields failing at once (which is exactly what full_clean() produces — it can flag several fields in one shot). It's a Python dictionary — a structure of key → value pairs. Here, each key is a field name (like "first_name", "phone"), and each value is a list of error message strings for that field. So it might look like:

# python
# {
#     "first_name": ["This field cannot be blank."],
#     "phone": ["Enter a valid phone number."],
# }

# .keys()
# Another dot, reaching further inside — this time calling a method (a function that belongs to the dictionary) rather than grabbing an attribute. .keys() means "give me back just the keys of this dictionary, not the values." Applied to the example above, e.message_dict.keys() would give you something containing "first_name" and "phone" — just the field names, with the error messages stripped away for now.

# Why the parentheses after keys?
# Because .keys() is a method, not a plain attribute — parentheses are how you call it, telling Python "actually run this action now," rather than just referring to it. Compare this to .message_dict, which has no parentheses, because it's just a stored value, not an action to perform.

# list(...)
# Now zoom out one more layer. e.message_dict.keys() doesn't hand back a plain Python list — it hands back a special view object (Django/Python's dict_keys type). Wrapping it in list(...) converts that view into an actual, ordinary Python list — something you can index into with square brackets, which is exactly what happens next. Without this list(...) wrapper, the [0] on the very end wouldn't work, because dict_keys objects don't support that kind of indexing.

# [0]
# Square brackets after something mean "reach inside this collection and grab one specific item, by its position." 0 is the very first position (Python always counts starting from zero, not one). So [0] means: "of all the field names that failed, just take the first one."

# Putting the right side together, innermost to outermost:
# "Get the dictionary of field-name → error-messages → get just the field names → turn that into a real list → grab the first one."

# Left side: field =
# We're storing that single field name — a string, like "phone" — into a new variable called field, so we can refer to it again on the next two lines without repeating this whole chain.

# Whole line, plain English:
# "Find out which field failed first, and remember its name."

# Line 2: message = e.message_dict[field][0]

# Right side, read left to right this time since there's no deep nesting — just a chain of two lookups:

# e.message_dict
# Same dictionary as before — field names mapping to lists of error messages.

# [field]
# This is different from .keys() — this is Python's standard dictionary lookup syntax: some_dict[some_key] means "give me the value stored under this specific key." Since field currently holds a string like "phone" (from line 1), this line means: "look up the value stored under the key "phone"" — which, per the dictionary shape shown earlier, is a list of error message strings for that one field, e.g. ["Enter a valid phone number."].

# [0]
# Same meaning as before — "grab the item at position zero." A field can technically have more than one error message attached (imagine both "too long" and "contains invalid characters" firing at once) — this line deliberately picks just the first one, rather than trying to combine or list all of them.

# Left side: message =
# Store that single string — the actual human-readable error text — into a variable called message.

# Whole line, plain English:
# "Now that we know which field failed, get its first error message."

# Beginner question you might be sitting with: why field on line 1 and then reuse it here instead of writing this whole thing in one line? Because field is needed twice — once here on line 2, and again on line 3 below. Storing it once avoids repeating list(e.message_dict.keys())[0] a second time, and gives the repeated value a name that makes line 3 easier to read.

# Line 3: raise AppValidationError(message, field=field)

# raise
# The verb. This stops the function's normal execution entirely and throws an exception up to whatever code called this function — exactly like return, except instead of handing back a normal value, it signals "something went wrong," and Python will keep propagating it upward until something catches it with a matching except.

# AppValidationError
# This is a class — your project's own custom exception type, imported at the top of the file. Writing AppValidationError(...) constructs a new instance of it, the same way User(...) constructed a new user earlier in this same function.

# (message, field=field)
# Two arguments being handed into the constructor:

# message — passed positionally (no keyword name in front) — this is presumably the exception's main text, whatever AppValidationError's first constructor parameter is defined to accept.
# field=field — passed by keyword. This is the one worth slowing down on, because the same word field appears on both sides of the = and means two different things. The left field (before the =) is the parameter name that AppValidationError's constructor expects — it's not a variable, it's a label telling Python "put this value into the slot named field." The right field (after the =) is our local variable from line 1 — the actual string value, like "phone". It's exactly the same situation as email=email you saw back in get_user_by_email — the coincidence that the parameter name and the variable name are spelled identically is common and intentional (it's the clearest possible naming), but they are not the same thing just because they look alike.

# Whole line, plain English:
# "Raise a new AppValidationError, carrying the error message as its main content, and tagging which field caused it."

# All three lines together, as one story

# "Find out which field failed first. Get that field's error message. Raise our own clean, application-level error carrying that message and naming the field — instead of letting Django's raw, dict-shaped ValidationError leak out to whoever called create_user."
# 6. Beginner questions, answered proactively

# Why full_clean() and a database UNIQUE constraint — isn't one enough?
# full_clean() alone is vulnerable to the race condition described above (check, then a gap, then insert). The database constraint alone would work but gives you a much less friendly error to catch and translate (IntegrityError carries far less structured detail than ValidationError.message_dict). Using both gives you a clean, informative error in the common case, and a hard guarantee against duplicates even in rare race conditions.

# Why does set_unusable_password() exist instead of just leaving password unset?
# Because Django's authentication system needs an explicit, unambiguous signal that "this account cannot currently log in with a password" — as opposed to accidentally storing an empty string or None in the password-hash field, which could behave unpredictably (or dangerously) depending on the authentication backend's exact comparison logic.

# Why is @transaction.atomic needed here when there's only one .save() call?
# Because full_clean() itself can trigger database queries (uniqueness checks), and there's a philosophy worth internalizing here: any function doing multiple logically-related database operations — reads or writes — that together represent "one meaningful unit of work" (creating a user) should be wrapped atomically, so that a failure partway through never leaves inconsistent, partial state.

# Why catch ValidationError in two completely separate places in this function (once around validate_password_strength, once around full_clean()), instead of one big try around everything?
# Because they mean different things and need different responses. A password-strength failure should always become an AppValidationError on the password field, full stop. A full_clean() failure needs to be inspected first — it might mean a duplicate email (a business rule violation) or some other field problem (a validation error) — those need to become different exception types. Splitting the try blocks keeps each one's error-translation logic simple and specific to what it's actually catching.

# 7. Design discussion

# Why translate Django's built-in exceptions into your own AppValidationError/BusinessRuleViolationError types at all, instead of letting ValidationError/IntegrityError propagate up?
# This is a boundary-layer design pattern: your service layer's job is to shield the rest of the application (GraphQL resolvers, eventually the frontend) from framework/database-specific exception types. A GraphQL mutation can catch AppValidationError and BusinessRuleViolationError generically and turn them into a consistent {success: false, errors: [...]} payload shape, without needing to know or care whether the underlying failure came from Django's ORM, a raw database constraint, or a custom validator. If Django's internals changed how they raise errors, only this translation layer would need updating — not every caller.

# Trade-off worth naming: this translation layer is only as trustworthy as its correctness — and as Bugs #1 and #2 show, if the translation logic itself has a subtle bug, you get the worst of both worlds: neither the clean application-level error you intended, nor the original framework error with its actual, informative message — just an unrelated AttributeError that obscures what really went wrong. Exception-translation code deserves the same scrutiny (and ideally, test coverage specifically exercising the failure paths, not just the happy path) as any other business logic.

# 8. DIY Recipe — build one like this yourself

# How to build your own "create + validate + translate errors" service function:

# Validate format-level concerns up front, before touching the database or building the model (email format, phone format) — fail fast on cheap checks.
# Handle sensitive fields (passwords) specially — never pass them as a plain constructor field; always route through the model's dedicated hashing method, with an explicit branch for "no password provided."
# Wrap the whole thing in @transaction.atomic if it involves more than one logical database step.
# Call full_clean() before save(), always — catching validation problems before they become a database round-trip.
# When catching a dict-based ValidationError, always read messages from e.message_dict[field], never from e.message — that attribute simply doesn't exist on this shape of error.
# Keep a separate except IntegrityError as a backstop for race conditions that slip past application-level validation, translating it to the same business error a caller would expect from the more common path.
# Type-hint every parameter, including plain booleans — don't let "obvious" defaults like is_active=True skip the hint just because the intent seems self-evident.
# 9. General pattern recognition

# This is the "validate → construct → save → translate exceptions" pattern — the most complete write-service shape you've seen so far:

# python
# @transaction.atomic
# def create_<thing>(*, <required fields>, <optional fields> = None) -> Model:
#     <run format-level validators>
#     obj = Model(<fields>)
#     <handle any special fields, e.g. hashing>
#     try:
#         obj.full_clean()
#         obj.save()
#         return obj
#     except ValidationError as e:
#         <translate into your app's error types, using e.message_dict correctly>
#     except IntegrityError:
#         <translate race-condition failures the same way>

# You'll reuse this exact shape for create_company, create_role, or any other "make a new top-level record with validation and duplicate protection" service.

# 10. Real project usage

# Directly behind a signup mutation or a staff "invite user" mutation:

# python
# def resolve_create_user(self, info, email: str, first_name: str, last_name: str, company_id: str) -> UserPayload:
#     actor = get_current_user(info)
#     require_permission(actor=actor, codename="staff.create_users")
#     company = get_company(company_id=company_id)  # hypothetical, same "safe lookup" pattern as get_user
#     try:
#         user = create_user(email=email, first_name=first_name, last_name=last_name, company=company, password=None)
#     except AppValidationError as e:
#         return UserPayload(success=False, errors=[e.to_error_response()])
#     except BusinessRuleViolationError as e:
#         return UserPayload(success=False, errors=[e.to_error_response()])
#     return UserPayload(success=True, user=user)
# 11. Common beginner mistakes

# ❌ The exact bugs in this file — assuming a caught ValidationError always has a .message attribute, when dict-constructed errors (from full_clean(), and possibly from multi-message validators) only expose .message_dict / .messages, not .message.

# ❌ Passing a plain-text password into the model constructor (User(password=password, ...)) instead of set_password() — stores an unhashed password directly in the database, a severe security bug.

# ❌ Calling save() without full_clean() first — skips validation entirely, relying only on whatever the database constraints happen to catch.

# ❌ Forgetting @transaction.atomic on a function with multiple database-touching steps, risking partial writes if something fails midway.

# ❌ Catching IntegrityError but not ValidationError, or vice versa — leaves one whole class of duplicate-detection (the race-condition case, or the common case) completely untranslated, letting a raw Django/database exception leak out to the caller.

# 12. Think like the original developer

# If you had to invent this yourself with no reference:

# What problem am I solving? "I need one trustworthy place that creates a user correctly — validated, password hashed properly, duplicates rejected cleanly — no matter which part of the app is asking for a new user."
# What inputs will I need? The required identity fields (email, name), optional contact/auth fields (phone, password), optional relationships (company), and a handful of permission-style flags with sensible defaults.
# What could go wrong? Malformed email/phone; a weak password; a duplicate email (caught either by application validation or, in a race condition, by the database itself); some other field failing model validation.
# How should I report errors? Never let framework-level exceptions leak to callers — translate everything into the application's own vocabulary, and make sure that translation logic actually reads the right attribute off the caught exception (the exact place this file currently gets it wrong).
# What should happen if everything works? Return the real, persisted User object — and only that, since the return type promises a User, never None, meaning every failure path must raise, not silently return something falsy.