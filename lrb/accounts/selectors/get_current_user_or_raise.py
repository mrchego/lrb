from __future__ import annotations
from typing import TYPE_CHECKING
import strawberry
from lrb.accounts.selectors import get_current_user
from lrb.core.exceptions import AppPermissionDeniedError

if TYPE_CHECKING:
    from lrb.accounts.models import User

def get_current_user_or_raise(info: strawberry.Info) -> User:
    current = get_current_user(info)
    if not current or not current.company_id:
        raise AppPermissionDeniedError("No company context.")
    return current


# Teaching: get_current_user_or_raise

# This is a small function, but it packs in a lot of Python patterns you'll see everywhere. Let's go through it completely.

# 1. What is it?

# This is a helper function that lives in your GraphQL layer. Its job: figure out who the current logged-in user is, and refuse to continue if that user isn't properly set up (not logged in, or not attached to a company).

# Let's name every piece before we explain how they fit together:

# from __future__ import annotations — a special "turn on a future Python feature now" import
# from typing import TYPE_CHECKING — a constant used to hide imports from Python at runtime
# import strawberry — brings in the Strawberry GraphQL library
# from lrb.accounts.selectors import get_current_user — imports a function from another file in your project
# from lrb.core.exceptions import AppPermissionDeniedError — imports a custom error type
# if TYPE_CHECKING: — a conditional block that only runs for type-checkers, not for real
# def — keyword that starts a function definition
# info: strawberry.Info — a parameter with a type hint
# -> User — a return type hint
# current = get_current_user(info) — calling a function and storing its result
# if not current or not current.company_id: — a conditional with not and or
# raise — keyword that throws an error
# return current — keyword that sends a value back to whoever called this function

# We'll walk through each of these.

# 2. How is it written? (syntax piece by piece)

# from X import Y
# This means: "go to module X, and pull out just the name Y so I can use it directly." Compare this to import strawberry, which imports the whole module, so you have to write strawberry.Info (module name + dot + thing inside it) to reach things inside it.

# . (dot)
# The dot means "go inside this thing and grab something from it." strawberry.Info means "go into the strawberry module and get the Info class." current.company_id means "go into the current object and get its company_id attribute." Same symbol, same meaning, every time: dot = look inside.

# : (colon) — three different jobs in this file

# After def get_current_user_or_raise(...): — colon says "the function body starts now, indented below."
# After if TYPE_CHECKING: and if not current...: — colon says "the block that runs if this is true starts now."
# Inside info: strawberry.Info — this colon is a type hint. It doesn't mean "block starts," it means "this parameter should be of this type." Same symbol, different job depending on where it sits — Python figures out which meaning from context.

# -> (arrow)
# This appears once: -> User. It means "this function, when it finishes, returns something of type User." It's purely for humans and type-checking tools — Python itself doesn't enforce it at runtime. If you wrote -> int here but returned a string, Python would let it happen; a type checker (like mypy) would complain.

# () (parentheses)
# Three uses here:

# After a function name (get_current_user(info)) — "call this function, and here's the input I'm handing it."
# After def name(...) — "here is the list of inputs this function accepts."
# Around exception message: AppPermissionDeniedError("No company context.") — this is calling the exception class like a function, to build an error object with that message inside it.

# = (equals)
# current = get_current_user(info) — this is assignment, not "equals" like in math. It means: "run the right side first, get its result, then store that result in a new name called current." Read assignment lines right-to-left.

# 3. Signature — broken into pieces
# python
# def get_current_user_or_raise(info: strawberry.Info) -> User:
# Piece	Meaning
# def	"I am defining a function starting here"
# get_current_user_or_raise	the function's name — you'll call it later by typing this exact name
# (	start of the parameter list
# info	the name of the one parameter — a placeholder that gets filled in with a real value when someone calls the function
# : strawberry.Info	type hint — "whatever gets passed in as info should be a strawberry.Info object"
# )	end of the parameter list
# -> User	"this function will return something of type User"
# :	"function body begins below, indented"

# Notice the function name itself is documentation: get_current_user (fetch it) or raise (throw an error if you can't). Reading a good function name should tell you its whole job without opening it.

# 4. Body — line by line
# python
# current = get_current_user(info)

# Python calls the imported function get_current_user, handing it info (which — as you'll learn in "Connections" below — usually carries the request/context). Whatever that function returns (either a User object or None) gets stored under the name current.

# python
# if not current or not current.company_id:

# Read this right side first, then left, then whole line — like your reading-code habit says.

# not current — current is "truthy" if it holds a real object, "falsy" if it's None. not current flips that: it's True when there is no user.
# not current.company_id — if current does exist, check its company_id field. not flips again: True when company_id is missing or None.
# or — combines the two checks: "if EITHER of these is true, run the block below." Python is smart here (called short-circuiting): if not current is already True, Python won't even bother checking current.company_id — good thing too, because if current is None, trying to read .company_id on it would crash with an AttributeError. The or order isn't random — it protects the second check.
# python
#     raise AppPermissionDeniedError("No company context.")

# If either failure condition was true, Python builds an AppPermissionDeniedError object carrying the message "No company context.", then immediately stops the function and throws it upward. Nothing after raise in this function will run.

# python
# return current

# If we got here, both checks passed — current is a real user with a company. Python hands that current object back to whoever called this function.

# 5. Why?

# Why write a separate function for this instead of checking inline everywhere?
# Because "is there a logged-in user with a company?" is a check you'll need in many resolvers across your GraphQL API (orders, staff, products — anywhere that's scoped to a company). Writing it once here means every resolver just calls get_current_user_or_raise(info) and either gets a guaranteed-valid user back, or the error is already thrown and they don't need to think about it. This is the DRY principle (Don't Repeat Yourself) — you write the check once, trust it everywhere.

# Why raise an exception instead of returning None on failure?
# If it returned None, every single caller would have to remember to check if user is None: handle it somehow. People forget that check, and bugs slip through (a resolver might accidentally run business logic with None as "the user"). By raising instead, Python forces the caller to deal with it — either the exception propagates up and gets turned into a proper GraphQL error automatically, or the caller wraps it in a try/except deliberately. The function's own name — ..._or_raise — is honest about this contract.

# Why check company_id at all, not just "is there a user"?
# This tells us something about your RBAC project: permissions and actions are scoped per company (this matches your project's company-scoped architecture). A user who exists but isn't attached to a company yet (maybe mid-signup) shouldn't be treated as fully authorized. This function encodes "valid session" as both conditions together.

# 6. Connections

# What comes in: info: strawberry.Info. In Strawberry GraphQL, every resolver function automatically receives an info object if it asks for one as a parameter. It carries the current GraphQL request — including things like the HTTP request, the logged-in session, and request-scoped context. This function doesn't build info — it receives it from whatever resolver calls it, and passes it straight through to get_current_user(info) (a selector — matching your project's service/selector split, where selectors read data and services write it).

# What goes out: Either a User object (success path) or an AppPermissionDeniedError exception (failure path) — never both, and never something in between.

# Where it fits in your project: This will get called at the top of your GraphQL mutations/resolvers, before any real work happens — a gatekeeper. For example, a mutation to create an order would likely start with:

# python
# user = get_current_user_or_raise(info)

# before doing anything company-scoped. This matches your project's pattern: "mutations are thin orchestration layers" — this is exactly the kind of thin, first line a mutation should have, before it hands off to a service.

# TYPE_CHECKING connection: User is only imported "for real" when a type-checking tool analyzes your code — not when Python actually runs it. More in section 7.

# 7. Advanced concepts (not skipped)

# A) from __future__ import annotations
# Normally, when Python runs a function definition, it evaluates every type hint immediately — meaning it would need the real User class available right then. This import changes that behavior: it tells Python to treat all type hints as plain text (strings) instead of evaluating them immediately. They're only turned into real objects later, if and when a tool like mypy asks for them.

# Why does this matter here? Because of the next concept:

# B) TYPE_CHECKING and circular imports

# python
# if TYPE_CHECKING:
#     from lrb.accounts.models import User

# TYPE_CHECKING is a special constant that is always False when your actual program runs, but tools like mypy or your editor pretend it's True when they analyze your code. So:

# When Python actually runs your app: this if block never executes. User is never really imported into this file.
# When a type-checker or your editor reads the file: it pretends the if is True, imports User, and uses it to check that your -> User hint makes sense and to give you autocomplete.

# Why go through this trouble instead of just importing User normally at the top? Because of circular imports — a very common real-world problem. If lrb.accounts.models (where User lives) also, somewhere down its own chain, ends up importing something from this file's module, you'd get an import loop that crashes Python when it starts up. By only "importing" User for type-checking purposes, you get the type-safety benefit without creating a real runtime dependency between the two files. This trick only works because of from __future__ import annotations — without it, Python would try to actually evaluate -> User at run time and crash with NameError: name 'User' is not defined.

# C) Custom exceptions
# AppPermissionDeniedError is not a built-in Python error — it's a class your project defines (in lrb.core.exceptions), almost certainly inheriting from Python's built-in Exception. Custom exception classes let your project distinguish types of failure ("permission denied" vs "not found" vs "validation error") so that higher-level code (like your GraphQL error formatter) can catch them and turn each one into the right kind of API response, instead of one generic crash.

# D) Truthiness (not current)
# In Python, objects don't need to be literally True/False to be used in an if. Python asks: "is this thing empty/zero/None?" If yes, it's treated as False (falsy). None is falsy. So not current is really asking "is current nothing?" — a very common, idiomatic Python check, cleaner than writing if current is None: when you don't care about telling None apart from other falsy values.

# 8. Small example

# Imagine a tiny stand-in version, no GraphQL, just plain Python, to see the shape clearly:

# python
# def get_logged_in_user_or_raise(session):
#     user = session.get("user")          # like get_current_user(info)
#     if not user or not user.get("company_id"):
#         raise ValueError("No company context.")
#     return user

# session_ok = {"user": {"name": "Amina", "company_id": 5}}
# session_bad = {"user": {"name": "Amina", "company_id": None}}

# print(get_logged_in_user_or_raise(session_ok))   # returns the user dict
# get_logged_in_user_or_raise(session_bad)          # raises ValueError

# Same shape: fetch → validate → raise-or-return.

# 9. What you should remember
# fn_or_raise naming pattern: a function name ending in _or_raise (or _or_404, etc.) is a promise — it always gives you a valid value, or it throws, never a silent None. Trust that contract; don't add extra if user is None checks after calling it.
# not x or not x.attr needs order: when checking "does this exist AND does its field exist," always check existence first — Python's or/and short-circuiting means the second check is only run if needed, which protects you from crashing on None.
# TYPE_CHECKING + from __future__ import annotations is a standard pair for breaking circular imports while keeping type hints. When you see this pattern, know it means "this import only exists for tools, not for the running program."
# Gatekeeper functions belong at the top of orchestration code. This function is designed to be the very first line in a resolver/mutation — validate access before doing any real work.
# Custom exceptions carry meaning. Raising AppPermissionDeniedError instead of a generic error lets the rest of the system (like error formatting) respond appropriately based on what kind of failure happened.