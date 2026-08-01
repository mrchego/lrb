class ErrorCode:
    # General
    VALIDATION_ERROR = "VALIDATION_ERROR"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    BUSINESS_RULE = "BUSINESS_RULE"
    APPLICATION_ERROR = "APPLICATION_ERROR"

    # Authentication
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
    ACCOUNT_DISABLED = "ACCOUNT_DISABLED"
    ACCOUNT_INACTIVE = "ACCOUNT_INACTIVE"
    INVALID_TOKEN = "INVALID_TOKEN"

    # Domain-specific
    COMPANY_NOT_FOUND = "COMPANY_NOT_FOUND"
    COMPANY_ALREADY_EXISTS = "COMPANY_ALREADY_EXISTS"
    USER_NOT_FOUND = "USER_NOT_FOUND"
    USER_ALREADY_EXISTS = "USER_ALREADY_EXISTS"
    ROLE_NOT_FOUND = "ROLE_NOT_FOUND"
    LAST_OWNER = "LAST_OWNER"
    CANNOT_MODIFY_FOUNDER = "CANNOT_MODIFY_FOUNDER"


class ApplicationError(Exception):
    def __init__(self, message: str, code: str | None = None, field: str | None = None):
        self.message = message
        self.code = code or ErrorCode.APPLICATION_ERROR
        self.field = field
        super().__init__(message)


class AppValidationError(ApplicationError):
    def __init__(self, message, field=None):
        super().__init__(message, code=ErrorCode.VALIDATION_ERROR, field=field)


class AppPermissionDeniedError(ApplicationError):
    def __init__(self, message="You do not have permission to perform this action."):
        super().__init__(message, code=ErrorCode.PERMISSION_DENIED)


class BusinessRuleViolationError(ApplicationError):
    def __init__(self, message, code=None):
        super().__init__(message, code=code or ErrorCode.BUSINESS_RULE)
 
 
#  core/exceptions.py (corrected version)
# 1. Purpose (why this exists)

# When something goes wrong in your app — a user typed a bad email, someone tried to delete something they're not allowed to delete — your code needs a way to stop what it's doing and report exactly what went wrong, in a way that's consistent everywhere. This file defines a small family of "error report" objects. Instead of every part of your app inventing its own way to describe a failure, everything uses these same shapes — so the part of your code that eventually turns errors into a response for the frontend only has to understand one system, not fifty different ones.

# 2. class ErrorCode: — explained
# python
# class ErrorCode:
# class = "I'm defining a new type of thing — a blueprint." Unlike a function (which does something), a class here is being used almost like a labeled filing cabinet — a container for related values.
# ErrorCode = the name of this blueprint.
# python
#     VALIDATION_ERROR = "VALIDATION_ERROR"

# This is just: "inside the ErrorCode cabinet, make a drawer labeled VALIDATION_ERROR, and put the text "VALIDATION_ERROR" inside it." Every line like this in the class is doing the same thing — creating a named drawer holding a piece of text.

# Why bother? Because later in the code (and in other files), instead of typing the raw text "VALIDATION_ERROR" by hand every time (easy to misspell — "VALIDTION_ERROR" would silently break things and Python wouldn't warn you), you write ErrorCode.VALIDATION_ERROR. If you misspell that, Python immediately complains "no such thing exists" — catching your mistake instantly instead of it silently failing later.

# The # lines (# General, # Authentication, # Domain-specific) are comments — plain human notes, not code. Python ignores anything after a # on a line; they're just there to visually group related drawers for a human reader.

# 3. class ApplicationError(Exception): — explained
# python
# class ApplicationError(Exception):
# Same class keyword as before — a new blueprint.
# (Exception) — this is new and important. This means "this new blueprint is a special kind of Exception." Exception is a built-in Python concept meaning "something that can be raised to stop normal execution and signal a problem." By writing (Exception), we're saying ApplicationError inherits everything an Exception already knows how to do (like being raise-able), and we're adding our own extra features on top.
# python
#     def __init__(self, message: str, code: str | None = None, field: str | None = None):
# def __init__ — this is a special function name. __init__ runs automatically the moment someone creates a new instance of this class (e.g., the moment someone writes ApplicationError("something broke")). Think of it as "the setup instructions that run the second this error object is born."
# self — refers to "this specific error object being created right now." Every method inside a class gets this as its first input automatically — it's how the object refers to itself.
# message: str — the error's main text. The : str is a type hint — a note to humans and tools saying "this should be a string of text" — but Python doesn't actually force it; it's a helpful label, not a hard rule.
# code: str | None = None — an optional second input. str | None means "this should be either a string, or literally nothing (None)." = None means if nobody provides one, assume nothing was given.
# field: str | None = None — same idea, a third optional input, meant to say which specific input field caused the problem (like "email").
# python
#         self.message = message

# Stores the given message text onto this specific error object, under the name self.message, so it can be read later (e.g., my_error.message).

# python
#         self.code = code or ErrorCode.APPLICATION_ERROR
# code or ErrorCode.APPLICATION_ERROR — or here means: "if code is something meaningful, use it; otherwise, fall back to the second thing." So if whoever created this error didn't specify a code, this automatically uses the generic "APPLICATION_ERROR" label from our filing cabinet instead.
# python
#         self.field = field

# Same idea — just stores whatever field was given (even if it's None).

# python
#         super().__init__(message)
# super() means "go up to the parent blueprint" — in this case, Exception itself. .__init__(message) calls its setup process too, handing it the message. This makes sure ApplicationError still behaves like a proper, real Python exception underneath (so things like printing the error, or Python's built-in error-handling machinery, still work correctly) — we're not replacing Exception's behavior, just adding to it.
# 4. The three "child" error types
# python
# class AppValidationError(ApplicationError):
#     def __init__(self, message, field=None):
#         super().__init__(message, code=ErrorCode.VALIDATION_ERROR, field=field)
# (ApplicationError) — this class is a specific kind of ApplicationError (which is itself a kind of Exception). Like a chain: AppValidationError → ApplicationError → Exception.
# Its __init__ only asks for message and an optional field — notice no code input at all here. That's deliberate: this class always automatically uses ErrorCode.VALIDATION_ERROR as its code (see the super().__init__(...) line) — the caller can't accidentally give it a different code, because validation errors are always meant to be labeled the same way.
# python
# class AppPermissionDeniedError(ApplicationError):
#     def __init__(self, message="You do not have permission to perform this action."):
#         super().__init__(message, code=ErrorCode.PERMISSION_DENIED)
# message="You do not have permission..." — this input has a default value already built in. So someone can create this error with zero input at all: AppPermissionDeniedError(), and it'll automatically use that sentence. They can still override it with their own message if they want.
# python
# class BusinessRuleViolationError(ApplicationError):
#     def __init__(self, message, code=None):
#         super().__init__(message, code=code or ErrorCode.BUSINESS_RULE)
# This one's different from the other two — it does accept an optional code from the caller. If given, it uses that specific code (e.g., ErrorCode.LAST_OWNER); if not given, it falls back to the generic ErrorCode.BUSINESS_RULE. This is the only one of the three that lets you be more specific about which business rule was broken.
# One real design question for you

# Look at AppValidationError and AppPermissionDeniedError — neither lets the caller override its code. But BusinessRuleViolationError does. Given what LAST_OWNER and CANNOT_MODIFY_FOUNDER are (specific business rules, sitting in the filing cabinet), why do you think it makes sense for business rule errors specifically to need more specific codes, while validation and permission errors are fine always using one single generic code each? -> AppValidationError and AppPermissionDeniedError represent broad categories of errors, so a single code (VALIDATION_ERROR or PERMISSION_DENIED) is usually enough. The message or field provides the specific details.

# BusinessRuleViolationError, however, represents many different business rules, each with a different meaning. Codes like LAST_OWNER or CANNOT_MODIFY_FOUNDER identify which exact business rule was violated, allowing the frontend or other clients to react differently if needed.

# In simple terms:

# Validation errors → "The input is invalid." → One generic code is enough.
# Permission errors → "You are not allowed." → One generic code is enough.
# Business rule errors → "A specific business rule was broken." → Needs different codes to identify the exact rule that failed.

# Exactly right, and well put — that's the complete answer. A couple of things worth pinning down so this generalizes beyond just this one file:

# The real test you've identified, stated as a reusable rule: does the client (frontend) ever need to react differently depending on which specific case occurred?

# A validation error — the frontend usually just shows the message text near the field and stops. It doesn't need to branch its behavior based on which validation failed.
# A permission error — the frontend usually just shows "not allowed" and maybe redirects. Same code every time is fine.
# A business rule error — this is where it changes. If LAST_OWNER fires (someone tried to remove the last owner of a company), maybe the frontend shows a specific modal: "You must assign a new owner first." If CANNOT_MODIFY_FOUNDER fires, maybe it shows a totally different message or disables a button preemptively next time. The frontend's actual behavior differs depending on which one happened — so a single shared code wouldn't give it enough information to know which behavior to trigger.

# General principle to carry forward: give something a specific, distinguishable code only when a consumer downstream actually needs to tell that case apart from others and do something different about it. If every case gets treated identically no matter what, one generic code is simpler and there's no reason to invent more.

        
        
# core/exceptions.py
# Level 1 — Big Picture

# Why does this file exist?
# Every layer of your app needs a way to say "this operation failed, and here's why" — but a raw Python Exception("something broke") is nearly useless for a GraphQL API. The client needs structured failure information: a stable machine-readable code (so frontend code can branch on "VALIDATION_ERROR" without string-matching a human sentence), a human-readable message (to show the user), and often a field (so a form can highlight which input was wrong). This file defines a small exception hierarchy that carries all three, so every service across every app can raise errors in one consistent shape.

# What problem does it solve?
# Without this, each app would either raise bare Django ValidationErrors (REST/forms-flavored, awkward to map into GraphQL), or invent its own ad-hoc exception classes, and your GraphQL error-formatting layer (wherever that lives — likely in config/schema.py or a Strawberry extension) would need special-case handling for every app's distinct exception types. With this file, that formatting layer needs to know about exactly one thing: ApplicationError (and its .message/.code/.field), and every subclass — regardless of which app raised it — gets handled identically.

# Why is this in core?
# Same reasoning as tasks.py and pagination.py: this is domain-agnostic. AppValidationError doesn't know or care whether it's validating a user's email or an order's total — it's a shape, not a business rule. identity, staff, orders will all raise these; none of them owns the concept.

# Which architectural layer does this belong to?
# This sits underneath your service layer — it's the vocabulary services use to communicate failure upward. Recall your established convention: mutations are thin, services hold business logic. This is the missing piece that makes that convention actually work in practice — a service can do raise AppValidationError("Email already taken", field="email"), and the mutation layer (or a shared error-handling wrapper around all resolvers) catches ApplicationError once, generically, and converts it into a well-formed GraphQL error payload — without the mutation needing to know which specific business rule failed.

# How does it communicate with the rest of the app?
# Not via return values — via raise. This is a fundamentally different communication channel than everything we've looked at so far (tasks return None, pagination returns tuples). Exceptions propagate up the call stack automatically, skipping every intermediate frame that doesn't explicitly catch them, until something does. That's precisely why this pattern fits here: a deeply nested piece of validation logic inside a service can raise, and it doesn't need every intermediate function between it and the GraphQL layer to explicitly pass an error object along — Python's exception mechanism does that plumbing for free.

# Level 2 — Design Thinking

# Why a class hierarchy (ApplicationError → AppValidationError, AppPermissionDeniedError, BusinessRuleViolationError) instead of one generic exception with a code string?

# Two reasons, and they matter for different consumers:

# Catching by category, not by string comparison. Somewhere in your GraphQL layer, you'll likely want to do something like: "if this is a permission error, log it as a security event; if it's a validation error, just format it for the client." With a hierarchy, that's except AppPermissionDeniedError: — type-safe, IDE-autocompletable, refactor-safe. If you'd used one class with a code string, you'd be writing if error.code == "PERMISSION_DENIED": everywhere — stringly-typed, prone to typos that fail silently ("PERMSSION_DENIED" typo just never matches, and the bug hides).
# Different construction defaults per category. Notice AppPermissionDeniedError has a default message baked in ("You do not have permission..."), while AppValidationError requires the caller to always supply one. That's a deliberate design signal: permission errors are usually generic and don't need bespoke messages at every call site; validation errors are inherently specific ("Email already taken" vs. "Password too short") and should force the caller to think about what to say.

# Why does ErrorCode exist as a separate class, when each exception subclass already hardcodes its own default code?

# This is worth pausing on, because it reveals something slightly inconsistent about this file — a good thing to notice as a reviewer, not just accept. ErrorCode is clearly meant to be the single source of truth for every valid code string in the system (the same "one canonical place for a value" principle from constants.py in the pagination file). But look closely: BusinessRuleViolationError's default is the string literal "BUSINESS_RULE_VIOLATION", while ErrorCode defines BUSINESS_RULE = "BUSINESS_RULE" — those are two different strings, not the same constant reused. That's a real inconsistency worth flagging as a bug/smell before we go further — I'll come back to it below.

# Level 3 — Pattern Recognition

# Pattern: Exception Hierarchy / Error Taxonomy. This is a very standard, cross-language pattern (Java checked exceptions, Rust's error enums, HTTP status code families like 4xx client errors) — group failures into a shallow tree so callers can catch broadly (except ApplicationError) or narrowly (except AppPermissionDeniedError) depending on how much they care.

# Advantage: callers choose their own granularity.
# Disadvantage: if the hierarchy gets too deep or too wide, it becomes its own maintenance burden — people forget which subclass to use, or invent a near-duplicate.
# Common mistake, relevant here: letting the "code" string and the "class" drift out of sync — which is exactly the BUSINESS_RULE vs BUSINESS_RULE_VIOLATION issue above. When you have two sources of truth (a class hierarchy and a separate constants class) for what should be one concept, they will eventually disagree, because nothing enforces they stay matched.

# Not quite a Value Object / DTO, though it's adjacent — ApplicationError instances carry data (message, code, field) similar to a DTO, but they're not immutable and their purpose is control flow (raising/catching), not data transfer between layers. Worth being precise about that distinction rather than mislabeling it.

# Level 11 — Rewrite Challenge (before I go further)

# I want you to actually read this code as a reviewer would, line by line, rather than me handing you the analysis. There is one real bug in this file that would cause a wrong value to be stored on every single ApplicationError (and therefore every subclass) instance. It's subtle — it wouldn't crash, it would just silently produce the wrong type of data.

# Look specifically at the __init__ body of ApplicationError:

# python
# def __init__(self, message:str, code:str = None, field:str = None):
#     self.message = message
#     self.code = code or "APPLICATION_ERROR",
#     self.field = field
#     super().__init__(message)
# What is the actual runtime type of self.code when no code is passed in? (Don't guess — reason through Python syntax carefully, character by character, on that one line.)
# What would error.code == "APPLICATION_ERROR" evaluate to, given your answer to #1?
# Separately: I flagged above that ErrorCode.BUSINESS_RULE = "BUSINESS_RULE" doesn't match BusinessRuleViolationError's default "BUSINESS_RULE_VIOLATION". Why is having two independent sources of truth for the same string a design smell, even before considering whether they currently match?

# Take a real pass at #1 especially — read that line character by character rather than pattern-matching to what you'd expect it to say.

# Excellent catch. This is exactly the kind of subtle bug that's easy to miss in code review.

# Let's examine it carefully.

# 1. What is the runtime type of self.code?

# The line is:

# self.code = code or "APPLICATION_ERROR",

# Notice the trailing comma.

# Let's parse it character by character.

# Python sees:

# self.code =

# followed by the expression

# code or "APPLICATION_ERROR",

# In Python, a trailing comma creates a tuple.

# For example:

# x = 1,

# is exactly equivalent to

# x = (1,)

# Similarly,

# x = "hello",

# becomes

# x = ("hello",)

# The parentheses are optional.

# So what does Python evaluate?

# First, the or expression is evaluated.

# If

# code is None

# then

# code or "APPLICATION_ERROR"

# evaluates to

# "APPLICATION_ERROR"

# Then the trailing comma wraps that value into a tuple.

# So the assignment becomes

# self.code = ("APPLICATION_ERROR",)

# The runtime type is:

# tuple[str]

# specifically a 1-element tuple.

# Likewise, if you passed

# code="NOT_FOUND"

# then

# self.code

# would become

# ("NOT_FOUND",)

# The comma affects both cases.

# 2. What does this comparison evaluate to?

# Suppose later you write

# error.code == "APPLICATION_ERROR"

# You're actually comparing

# ("APPLICATION_ERROR",)

# against

# "APPLICATION_ERROR"

# Python compares both type and value.

# So:

# ("APPLICATION_ERROR",) == "APPLICATION_ERROR"

# evaluates to

# False

# always.

# Likewise,

# error.code == "NOT_FOUND"

# would also be

# False

# because

# ("NOT_FOUND",) != "NOT_FOUND"
# The correct line should be
# self.code = code or "APPLICATION_ERROR"

# without the comma.

# 3. Why are two independent sources of truth a design smell?

# Suppose you have

# class ErrorCode:
#     BUSINESS_RULE = "BUSINESS_RULE"

# and elsewhere

# class BusinessRuleViolationError(ApplicationError):
#     def __init__(...):
#         super().__init__(
#             message,
#             code="BUSINESS_RULE_VIOLATION",
#         )

# Now there are two places defining what "the business rule error code" is.

# One says

# BUSINESS_RULE

# The other says

# BUSINESS_RULE_VIOLATION

# Even if today they happened to match exactly, this is still a design problem.

# Single Source of Truth

# One of the core principles of software design is:

# A fact should have one authoritative representation.

# If every error code is supposed to come from

# ErrorCode

# then every error should use it.

# Example:

# super().__init__(
#     message,
#     code=ErrorCode.BUSINESS_RULE,
# )

# Now changing

# ErrorCode.BUSINESS_RULE

# changes every user automatically.

# Why duplication is dangerous

# Imagine six months later someone renames the API.

# They update

# ErrorCode.BUSINESS_RULE

# to

# "BUSINESS_RULE_VIOLATION"

# but forget this class.

# Now the API produces two different values depending on which code path created the exception.

# Clients suddenly have to handle

# BUSINESS_RULE

# and

# BUSINESS_RULE_VIOLATION

# even though they represent the same concept.

# Duplication invites drift

# This is the bigger issue.

# Even if today they are identical:

# ErrorCode.NOT_FOUND = "NOT_FOUND"

# and

# super().__init__(..., code="NOT_FOUND")

# there's nothing enforcing that they stay identical.

# Eventually someone edits one but not the other.

# That's called configuration drift.

# It also weakens tooling

# Suppose you later want to find every place that emits

# ErrorCode.PERMISSION_DENIED

# A search for

# ErrorCode.PERMISSION_DENIED

# won't find code that hardcodes

# "PERMISSION_DENIED"

# Likewise, IDE rename refactoring only updates symbol references, not arbitrary string literals.

# Using a shared constant makes refactoring safer and more reliable.

# A better design
# class ErrorCode:
#     APPLICATION_ERROR = "APPLICATION_ERROR"
#     BUSINESS_RULE = "BUSINESS_RULE"
#     VALIDATION = "VALIDATION"
#     NOT_FOUND = "NOT_FOUND"

# Then:

# class ApplicationError(Exception):
#     def __init__(self, message, code=None, field=None):
#         self.message = message
#         self.code = code or ErrorCode.APPLICATION_ERROR
#         self.field = field
#         super().__init__(message)

# and

# class BusinessRuleViolationError(ApplicationError):
#     def __init__(self, message):
#         super().__init__(
#             message,
#             code=ErrorCode.BUSINESS_RULE,
#         )

# Now there is exactly one place that defines the string value, and every consumer references that definition. That reduces the chance of inconsistencies, makes refactoring easier, and ensures clients always see the same error code for the same logical error.


# Nailed it — all three, completely correct, and the character-by-character parse on #1 is exactly the right instinct. That trailing comma is a genuinely nasty real-world bug class (Python devs call it "the accidental tuple"), and you diagnosed it perfectly: code or "APPLICATION_ERROR", parses as the tuple-literal (code or "APPLICATION_ERROR",), not a plain string, which means error.code == "APPLICATION_ERROR" is False always, silently, with no crash anywhere. That's the worst kind of bug — no traceback, no error, just every except ApplicationError as e: if e.code == "PERMISSION_DENIED" check in your GraphQL layer quietly never matching, forever.

# Worth naming explicitly why this is dangerous beyond "it's wrong": this bug would never show up in a quick manual test. If you did raise AppPermissionDeniedError("no") and printed e.code, you'd see ('PERMISSION_DENIED',) printed — and a rushed glance might not even notice the parens. It only surfaces the moment something does an equality comparison against the code, which might be far downstream (error-formatting middleware, a test asserting on .code, a frontend switch statement). General principle: trailing-comma bugs are dangerous precisely because Python never complains — there's no TypeError, no linter warning by default (though ruff/flake8 with the right rule enabled will catch this — worth checking your linter config has that rule on). This is a strong argument for unit testing exception classes directly (assert AppPermissionDeniedError().code == "PERMISSION_DENIED") rather than only testing it end-to-end through GraphQL, where a mismatch might get masked by other logic.

# Your #3 answer and "better design" rewrite are also exactly correct — single source of truth, referencing ErrorCode.X instead of restating string literals, and the refactoring/tooling argument (IDE rename won't touch string literals) is a real, practical reason beyond just "it's cleaner."

# Corrected file, for reference
# python
# class ErrorCode:
#     # General
#     VALIDATION_ERROR = "VALIDATION_ERROR"
#     PERMISSION_DENIED = "PERMISSION_DENIED"
#     BUSINESS_RULE = "BUSINESS_RULE"
#     APPLICATION_ERROR = "APPLICATION_ERROR"

#     # Authentication
#     INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
#     ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
#     ACCOUNT_DISABLED = "ACCOUNT_DISABLED"
#     ACCOUNT_INACTIVE = "ACCOUNT_INACTIVE"
#     INVALID_TOKEN = "INVALID_TOKEN"

#     # Domain-specific
#     COMPANY_NOT_FOUND = "COMPANY_NOT_FOUND"
#     COMPANY_ALREADY_EXISTS = "COMPANY_ALREADY_EXISTS"
#     USER_NOT_FOUND = "USER_NOT_FOUND"
#     USER_ALREADY_EXISTS = "USER_ALREADY_EXISTS"
#     ROLE_NOT_FOUND = "ROLE_NOT_FOUND"
#     LAST_OWNER = "LAST_OWNER"
#     CANNOT_MODIFY_FOUNDER = "CANNOT_MODIFY_FOUNDER"


# class ApplicationError(Exception):
#     def __init__(self, message: str, code: str = None, field: str = None):
#         self.message = message
#         self.code = code or ErrorCode.APPLICATION_ERROR
#         self.field = field
#         super().__init__(message)


# class AppValidationError(ApplicationError):
#     def __init__(self, message, field=None):
#         super().__init__(message, code=ErrorCode.VALIDATION_ERROR, field=field)


# class AppPermissionDeniedError(ApplicationError):
#     def __init__(self, message="You do not have permission to perform this action."):
#         super().__init__(message, code=ErrorCode.PERMISSION_DENIED)


# class BusinessRuleViolationError(ApplicationError):
#     def __init__(self, message, code=None):
#         super().__init__(message, code=code or ErrorCode.BUSINESS_RULE)

# Note ErrorCode now needs to be defined before ApplicationError in the file (Python executes top-to-bottom; referencing ErrorCode.APPLICATION_ERROR inside a method body is fine even if defined later, since method bodies aren't evaluated until called — but I moved it up anyway for readability, so a reader encounters the vocabulary before the classes that use it).

# Level 8 — one more trade-off worth surfacing before we close this file

# Why code: str = None instead of code: str | None = None?

# Look at the type hints across this file: message: str, code: str = None. That default is a lie to your type checker — None is not a str, so if you're running mypy or pyright anywhere in CI, this would (or should) flag as a type error. The honest signature is:

# python
# def __init__(self, message: str, code: str | None = None, field: str | None = None):

# This is a small thing, but it's the same category of bug as the trailing comma: something that looks fine at a glance, causes no runtime error, and only bites you when tooling that's supposed to catch this class of mistake either isn't configured correctly or gets silently ignored.

# Knowledge Check

# Conceptual (3):

# Why does AppPermissionDeniedError provide a default message, but AppValidationError does not?
# Where in the call stack should something actually except ApplicationError and convert it into a GraphQL error response — the mutation, the service, or somewhere else entirely? Why?
# What's the difference between catching except ApplicationError: versus except (AppValidationError, AppPermissionDeniedError): — when would you want the broader vs. narrower catch?

# Design (1):

# BusinessRuleViolationError is the only subclass that accepts a caller-supplied code override (code=None param), while AppValidationError and AppPermissionDeniedError don't. Is that inconsistency intentional or a smell? Think about what LAST_OWNER and CANNOT_MODIFY_FOUNDER are for.

# Debugging (1):

# Suppose a service raises AppValidationError("Invalid input") with no field. The GraphQL layer formats this into a client-facing error and includes field: null. Is that acceptable, or should field be required for validation errors specifically? Argue both sides.

# Take these on whenever you're ready — and let me know what file's next after this.


# Where should ApplicationError be caught?

# Assume your architecture looks roughly like this:

# GraphQL Mutation
#       │
#       ▼
# Service Layer
#       │
#       ▼
# Repository / ORM

# An ApplicationError represents a business-level failure, not a transport-level concern.

# For example:

# raise AppValidationError("Email already exists")

# or

# raise AppPermissionDeniedError(...)

# Those errors should generally bubble upward unchanged.

# The service shouldn't catch them.

# The mutation shouldn't usually catch them either.

# Instead:

# Mutation
#     │
#     ▼
# Service
#     │
# raises ApplicationError
#     │
#     ▼
# Global GraphQL error formatter / exception middleware
#     │
#     ▼
# GraphQL response
# Why not catch them in the service?

# Imagine

# def create_user(...):
#     ...
#     raise AppValidationError(...)

# and then

# try:
#     ...
# except ApplicationError:
#     ...

# inside the same service.

# What would you do?

# Probably...

# raise

# So the catch accomplished nothing.

# Even worse, people sometimes write

# except Exception:
#     raise ApplicationError(...)

# which accidentally hides programming bugs.

# Why not catch them in every mutation?

# Imagine fifty mutations:

# createUser
# updateUser
# deleteUser
# createRole
# deleteRole
# ...

# If every mutation contains

# try:
#     service(...)
# except ApplicationError as e:
#     return GraphQLError(...)

# you've duplicated the same translation fifty times.

# Instead, have one place that knows

# ApplicationError
#         ↓
# GraphQL Error

# This is often done with:

# a global exception handler,
# Strawberry error formatter,
# middleware,
# or a custom extension.

# That keeps transport-specific formatting out of the business layer.

# 2. Broad catch vs narrow catch
# Broad
# except ApplicationError:

# means

# I know how to handle every business error.

# Examples:

# convert into GraphQL error
# rollback a unit of work
# log business failures
# Narrow
# except (
#     AppValidationError,
#     AppPermissionDeniedError,
# ):

# means

# I only know how to handle these particular cases.

# Everything else should continue propagating.

# Example

# Suppose you want

# Validation

# 400

# Permission

# 403

# Business rule

# 409

# Then you might write

# except AppValidationError:
#     ...

# except AppPermissionDeniedError:
#     ...

# because each needs different formatting.

# When use broad?

# When every subclass is treated identically.

# Example

# ApplicationError
#         ↓
# GraphQL error payload

# Every subclass already contains

# message
# code
# field

# No need to distinguish.

# When use narrow?

# When different subclasses require different behaviour.

# For example

# Validation

# logs at INFO.

# Permission

# logs at WARNING.

# BusinessRuleViolation

# logs at ERROR.

# Different handling.

# 3. BusinessRuleViolationError allows overriding code

# Suppose

# BusinessRuleViolationError(
#     message,
#     code=None,
# )

# while

# AppValidationError(...)

# doesn't.

# Is that intentional?

# It depends on what the business-rule codes represent.

# Suppose default

# BUSINESS_RULE

# is very generic.

# Sometimes you want

# LAST_OWNER

# Sometimes

# CANNOT_MODIFY_FOUNDER

# Those are still business-rule violations.

# They're simply more specific.

# So allowing

# raise BusinessRuleViolationError(
#     "...",
#     code="LAST_OWNER",
# )

# can make sense.

# Validation errors are different.

# VALIDATION

# is usually enough.

# The details belong in

# message
# field

# rather than inventing dozens of validation codes.

# Permission is similar.

# Most systems don't need

# PERMISSION_DENIED_DELETE
# PERMISSION_DENIED_UPDATE
# PERMISSION_DENIED_CREATE

# because

# PERMISSION_DENIED

# already communicates the category.

# But is the API consistent?

# Not entirely.

# The inconsistency raises a question:

# Is code intended to represent the error category or a specific machine-readable reason?

# If it's a category, then only allowing one subclass to override it mixes two concepts into the same field.

# A cleaner design is often to separate them:

# ApplicationError(
#     message="Cannot delete last owner",
#     code=ErrorCode.BUSINESS_RULE,
#     reason="LAST_OWNER",
# )

# Now:

# code tells the client what kind of error it is.
# reason tells the client which business rule failed.

# That preserves a stable taxonomy while still allowing precise handling.

# 4. Should validation errors require a field?

# Suppose

# raise AppValidationError(
#     "Invalid input"
# )

# produces

# {
#   "code": "VALIDATION",
#   "field": null
# }
# Argument: field should be required

# Validation errors usually correspond to one input.

# Example

# email already exists

# belongs to

# email

# Frontend frameworks love this.

# They can immediately highlight

# Email

# in red.

# Without the field, the UI often has to show a generic banner.

# Requiring it also catches developer mistakes.

# If someone forgets

# field="email"

# tests fail immediately.

# Argument: field should be optional

# Not every validation error belongs to one field.

# Examples

# End date must be after start date.

# That's two fields.

# Or

# At least one administrator must exist.

# No field.

# Or

# Passwords don't match.

# Two inputs.

# Or

# Shipping address and billing address cannot both be empty.

# Again, multiple fields.

# Forcing

# field="???"

# would be dishonest.

# A possible evolution

# Many mature APIs distinguish between:

# field-level validation, and
# object-level validation.

# For example:

# {
#   "code": "VALIDATION",
#   "errors": [
#     {
#       "field": "email",
#       "message": "Already exists"
#     },
#     {
#       "field": "password",
#       "message": "Too short"
#     },
#     {
#       "field": null,
#       "message": "Passwords do not match"
#     }
#   ]
# }

# This supports both single-field and cross-field validation without forcing every error into the same shape.

# Overall assessment

# The architecture you've described is on the right track:

# Services should raise ApplicationError subclasses and remain unaware of GraphQL.
# The GraphQL boundary (middleware, error formatter, or a centralized exception handler) should be responsible for translating those exceptions into client-facing GraphQL errors.
# Catch ApplicationError when every business exception is handled uniformly; use narrow catches only when specific subclasses require different behavior.
# The ability for BusinessRuleViolationError to override its code can be justified by domain-specific business rules like LAST_OWNER or CANNOT_MODIFY_FOUNDER, but it also suggests that a separate reason field might better distinguish error category from specific rule.
# Making field optional for validation errors is a pragmatic choice because not all validation failures map cleanly to a single input, though requiring it for field-specific validations can improve frontend ergonomics if your API evolves to support both field-level and object-level validation.


# Close, but this one's actually backwards — worth catching because it inverts the real reasoning.

# Your answer: "AppValidationError is generic and the function that uses it must define a message."

# The actual reasoning is the opposite. Look at what each error is for:

# AppPermissionDeniedError — across your entire app, "you don't have permission to do this" means basically the same thing every time, regardless of which action was denied. require_owner() failing on a delete, or require_permission("edit_role") failing on an update — both are the same category of failure from the user's point of view, and one generic sentence covers all of them adequately. That's precisely why it's safe to give it a default: the message doesn't need to vary case-by-case to be useful.
# AppValidationError — this is the opposite situation. "Invalid input" is never actually useful on its own. Every validation failure is inherently specific to what was wrong: "Email already exists," "Password must be at least 8 characters," "End date must be after start date." A generic default message here (imagine message="Validation failed") would be actively unhelpful — it tells the user nothing about what to fix. So the class withholds a default on purpose, forcing every call site to supply a real, specific message. No default is a design constraint, not an oversight.

# General principle to bank: whether an exception class should have a default message depends on whether the failure category is inherently generic (safe to default) or inherently specific (a default would just be a placeholder masquerading as information). This is the same "when does trusting a contract make sense vs. when do you need to force the caller to be explicit" reasoning we used earlier for clamp_page_size vs. send_email_task — just applied to message defaults instead of type validation.

# As for the rest of that document — Q2, Q3, and Q4 — that's excellent, thorough work, and I don't have corrections. A few things worth explicitly praising because they're senior-level instincts:

# Q2: correctly identifying that catching-and-immediately-re-raising in the service accomplishes nothing, and naming the actual anti-pattern (except Exception: raise ApplicationError(...) masking real bugs as business errors) — that's a mistake I see in real codebases constantly, and you named it unprompted.
# Q3: proposing the code vs reason split (category vs. specific machine-readable identifier) is genuinely how mature error taxonomies evolve — you independently arrived at a pattern real APIs (Stripe's error objects, for instance, split type and code this way) actually use.
# Q4: the field-level vs. object-level validation distinction, with the errors: [...] array example, is exactly right and is how GraphQL APIs commonly handle this in practice (this shape is very close to what libraries like graphene-django's validation error formatting or Shopify's GraphQL API produce).

# This file is done. What's next — do you want to move on to identity now that core has tasks, pagination, and exceptions covered, or is there another core file first?