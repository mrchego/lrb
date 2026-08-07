import strawberry
from typing import Optional
from lrb.core.exceptions import ApplicationError, ErrorCode

@strawberry.type
class MutationError:
    message: str
    code: str
    field: Optional[str] = None
    
def format_application_error(error: ApplicationError) -> MutationError:
    return MutationError(
        message=error.message,
        code=getattr(error, 'code', ErrorCode.APPLICATION_ERROR),
        field=getattr(error, 'field', None)
    )
    
    
# 1. Purpose (Why this exists)

# What problem is this solving? Recall the whole point of exceptions.py: services raise ApplicationError (and its subclasses) so that business logic never needs to know anything about GraphQL. But eventually, something has to take that Python exception and turn it into an actual piece of data that Strawberry can send back to the frontend as part of a GraphQL response — GraphQL doesn't understand Python exceptions natively; it understands GraphQL types. This file is exactly that translation point: it defines what an error looks like as GraphQL data (MutationError), and a function that converts your Python ApplicationError objects into that shape.

# Why couldn't we just write the logic directly? You could write "error to GraphQL shape" conversion code inline, separately, inside every single mutation. But then, just like we saw with the try/except duplication argument in exceptions.py, you'd have the same conversion logic copy-pasted across every mutation in every app — and any future change (like adding a new field to every error) means editing every mutation instead of one function.

# When is this used in a real project? Inside every mutation resolver (or, more likely, in one shared wrapper/error-handling layer that all mutations pass through) — whenever a service raises an ApplicationError, this is the code that catches it and builds the actual MutationError object that gets included in the GraphQL response.

# What happens if this doesn't exist? Your GraphQL API would either crash with an unhandled Python exception leaking internal details to the client (a real security concern — stack traces can reveal file paths, library versions, even fragments of your code), or every mutation would need to hand-build this conversion itself, inconsistently.

# 2. Imports — explained like you've never programmed
# python
# import strawberry

# The core Strawberry package itself — recall from way back, this is imported as strawberry even though the installed package is called strawberry-graphql (a PyPI naming quirk). This gives you access to Strawberry's own tools for defining GraphQL types.

# python
# from typing import Optional

# typing is a module built into Python itself, providing tools purely for writing more precise/expressive type hints (remember: type hints are just notes for humans and tools, not enforced at runtime by plain Python — though Strawberry specifically does use them to build your actual GraphQL schema, which is different from normal Python type hints and explained more below). Optional is one specific tool from it — it means "this could be the given type, or it could be None." Optional[str] = "either a string, or nothing at all."

# python
# from lrb.core.exceptions import ApplicationError

# The base exception class from exceptions.py, imported here purely so this file can use it as a type hint on the function below — telling readers (and tools) "this function expects to receive an ApplicationError."

# 3 & 4. MutationError — the class
# python
# @strawberry.type
# class MutationError:

# Why @strawberry.type instead of @dataclass, even though this looks almost identical to BulkActionResult? This is genuinely important to understand precisely. @strawberry.type is Strawberry's own decorator — and it does something @dataclass doesn't: it registers this class as an actual GraphQL type, meaning Strawberry will include it in the GraphQL schema itself, generate the necessary GraphQL-protocol machinery around it, and make it something a GraphQL client can actually query fields from over the network. @dataclass only helps inside Python — it never talks to GraphQL at all. BulkActionResult didn't need to be a GraphQL type because it's an internal, Python-only helper object; MutationError does need to be one, because it's meant to travel all the way out to the frontend as part of an actual GraphQL response.

# Why a class here at all? Same reasoning as always — this bundles several related pieces of data (message, code, field) that always travel together as "one error," rather than three loose separate values.

# python
#     message: str
#     code: str
#     field: Optional[str] = None

# Notice this looks exactly like ApplicationError's own three attributes from exceptions.py — that's completely intentional; this is the GraphQL-facing mirror of that Python exception's shape.

# message: str — required (no default given), must be a string.
# code: str — required, must be a string.
# field: Optional[str] = None — optional, might be a string, might be None, and if not given, defaults to None. This maps directly onto ApplicationError.field, which — recall from exceptions.py — is also always optional, since not every error is tied to one specific input field (a permission error, for instance, has no relevant field).

# Why no @dataclass here as well, alongside @strawberry.type? You don't need both — @strawberry.type already does the equivalent work @dataclass would (auto-generating a constructor from these three attributes), specifically tailored for building GraphQL-compatible types. Using both would be redundant.

# 5. format_application_error — the body, line by line
# python
# def format_application_error(error: ApplicationError) -> MutationError:

# Signature, piece by piece:

# error: ApplicationError — one input, type-hinted as an ApplicationError (or any of its subclasses — AppValidationError, AppPermissionDeniedError, etc., since Python treats a subclass as compatible wherever the parent class is expected).
# -> MutationError — this function promises to hand back a MutationError object.
# python
#     return MutationError(
#         message=error.message,
#         code=getattr(error, 'code', 'APPLICATION_ERROR'),
#         field=getattr(error, 'field', None)
#     )

# Right side, then whole thing: we're constructing a brand-new MutationError object, filling in its three fields from the given error.

# message=error.message — straightforward: read .message directly off the exception, copy it over.
# field=getattr(error, 'field', None) — worth explaining getattr carefully, since it's new. getattr(object, "attribute_name", default_if_missing) is a built-in Python function meaning: "try to read this named attribute off this object; if it doesn't exist at all, don't crash — just give me back this fallback value instead." Compare this to just writing error.field directly — if error happened to be some exception type that didn't have a .field attribute at all, plain error.field would crash with an AttributeError. getattr(..., default) protects against that, gracefully falling back to None instead.
# code=getattr(error, 'code', 'APPLICATION_ERROR') — same defensive pattern, falling back to the literal string 'APPLICATION_ERROR' if .code is somehow missing.
# 6. Beginner questions, answered

# Why use getattr(..., default) at all, if every ApplicationError subclass we built already guarantees .code and .field exist (from exceptions.py's __init__)? Good instinct to ask — this connects directly to the design discussion below.

# Why is 'APPLICATION_ERROR' written as a raw string here, instead of ErrorCode.APPLICATION_ERROR? This is a real, catchable inconsistency — flagged explicitly below, since you've now seen this exact class of mistake twice already (exceptions.py's original BUSINESS_RULE mismatch).

# 7. Design Discussion

# Is the defensive getattr(...) actually necessary, given ApplicationError.__init__ guarantees .code and .field always exist?

# This is worth genuinely debating, not just accepting. Two ways to look at it:

# Argument for keeping it: this function's type hint says error: ApplicationError — but Python never enforces type hints at runtime. Nothing stops a bug elsewhere in the codebase from accidentally calling format_application_error(some_plain_exception), passing in a bare Exception or a completely unrelated object that was never actually an ApplicationError. If that happens, getattr(..., default) keeps this function safely degrading (with generic fallback values) instead of crashing with a confusing AttributeError deep inside your error-formatting layer — which would be a particularly bad place for a second, unrelated crash to happen while you're already handling a first error.
# Argument against it: it silently masks a real bug. If format_application_error is only ever called from a place that's already confirmed the exception is a genuine ApplicationError (e.g., an except ApplicationError: block, where Python itself guarantees the caught object really is one), then the defensive fallback can never actually trigger — and its presence might make a future reader think "oh, .code/.field might sometimes be missing," even though your own exceptions.py design guarantees they never are.

# A reasonable middle ground: keep the defensive getattr (cheap insurance against a rare, real category of bug), but fix the inconsistency: reference ErrorCode.APPLICATION_ERROR (the shared constant from exceptions.py) instead of retyping the raw string 'APPLICATION_ERROR' here. Exactly the same single-source-of-truth argument from before — if that default code string ever changes, this file should automatically stay correct rather than needing a separate manual update.

# python
# from lrb.core.exceptions import ApplicationError, ErrorCode

# def format_application_error(error: ApplicationError) -> MutationError:
#     return MutationError(
#         message=error.message,
#         code=getattr(error, 'code', ErrorCode.APPLICATION_ERROR),
#         field=getattr(error, 'field', None),
#     )
# 8. DIY Recipe — How to Build Your Own "Domain Object → GraphQL Type" Formatter
# Define a @strawberry.type class mirroring the shape of your internal Python object — same attribute names where it makes sense, so the mapping is obvious to read.
# Write one small function that takes your internal object and returns the GraphQL type, never the reverse (GraphQL types generally flow outward, toward the client — your internal domain objects shouldn't need to know GraphQL exists at all, matching the "services stay GraphQL-agnostic" principle from way back).
# Use getattr(obj, "attr", default) defensively when the input's exact type isn't 100%, runtime-guaranteed — cheap insurance against a mismatched caller, at the cost of a tiny bit of "could this actually be missing?" ambiguity for future readers.
# Always pull default/fallback values from your project's shared constants, never retype them as raw literals — keeping this formatter automatically in sync with wherever those defaults are canonically defined.
# 9. General Pattern Recognition
# Internal Python representation (ApplicationError)
#        ↓
# One small, dedicated "formatter" function
#        ↓
# External, protocol-facing representation (MutationError, a GraphQL type)

# This is the exact same "translate at the boundary" shape you've now seen repeatedly — Django's ValidationError → your AppValidationError (in require_valid_uuid), and now ApplicationError → MutationError (crossing from Python into GraphQL). Any time two different "worlds" need to talk (your business logic and an external protocol/format), you'll want exactly one narrow, dedicated translation function sitting at the seam between them — never scattered conversions duplicated throughout your codebase.

# 10. Real project usage

# This almost certainly gets called from a shared mutation wrapper or Strawberry extension that every mutation passes through — something like:

# python
# try:
#     result = some_service(...)
# except ApplicationError as e:
#     return SomeMutationPayload(errors=[format_application_error(e)])

# so that every single mutation in your schema — createUser, deleteRole, updateCompany — gets consistent, clean error formatting without each one reimplementing this conversion.

# 11. Common beginner mistakes
# ❌ Retyping raw string literals ('APPLICATION_ERROR') instead of referencing shared constants (ErrorCode.APPLICATION_ERROR) — the exact issue flagged above.
# ❌ Using @dataclass and @strawberry.type together unnecessarily, or using @dataclass alone when the type actually needs to be exposed over GraphQL (it wouldn't work — Strawberry wouldn't know to include a plain dataclass in its schema).
# ❌ Letting a raw Python exception (with a full internal traceback) leak directly into a GraphQL response instead of going through a formatter like this one — a real security/information-disclosure risk.
# ❌ Forgetting Optional[...] on a field that's genuinely allowed to be missing (like field), which would incorrectly tell Strawberry/GraphQL clients "this will always be present," breaking client-side code the first time it isn't.
# 12. Think like the original developer
# "My services raise ApplicationError — but GraphQL doesn't know what a Python exception is. I need something GraphQL does understand."
# "I'll define a GraphQL type that mirrors the shape of my error — message, code, and an optional field — so the frontend gets exactly the structured information it needs to show a helpful error."
# "I need one function whose only job is converting from my internal error shape to this GraphQL shape — so I never have to duplicate that conversion logic across every mutation."
# "Since I can't be 100% certain, at the Python level, that whatever gets passed in is really a fully-formed ApplicationError, I'll read its attributes defensively rather than assuming they're always there."
# "For consistency, my fallback values should reference the same shared constants as the rest of my error system — not be retyped by hand here."