from typing import Optional
from lrb.accounts.models import User

def get_user_by_email(*, email: str) -> Optional[User]:
    return User.objects.filter(email=email).first()


# 1. Purpose — Why this exists

# What problem is this solving?
# You constantly need to go from "an email address someone typed in" to "the actual User row in the database, if one exists." This happens during login, during password reset (finding who owns user@example.com before sending an OTP), during signup (checking if an email is already taken), and probably in your admin/staff tools when a staff member searches for a user.

# Why not just write the query directly wherever it's needed?
# Because "look up a user by email" isn't just one line — it's a decision: what happens if no one matches? Return None? Raise an error? Every place that needs this lookup would have to make (and remember to make) that decision consistently. Centralizing it means the decision is made once.

# When is this used in a real project?
# Anywhere you have an email address and need to know "does an account exist for this?" — login flows, password reset, signup validation, admin search.

# What breaks without it?
# Duplicated User.objects.filter(email=...) queries scattered everywhere, each one potentially handling the "not found" case differently — some might crash, some might return None, some might raise — making the codebase inconsistent and harder to trust.

# 2. Imports — explained like you've never programmed
# python
# from typing import Optional
# from lrb.accounts.models import User

# Same two imports you've now seen before, so let's move quickly but not skip anything:

# from typing import Optional — typing is a module built into Python itself (nothing to install). Optional is a tool for describing, to a human reader, "this could be the given type, or it could be None." It changes nothing about how the code runs — it's documentation with teeth, since editors and type checkers can read it too.
# from lrb.accounts.models import User — lrb.accounts.models is a dotted path through your own project's folders (lrb → accounts app → models.py file), not something built into Python or Django. User is your project's own custom user model, written by you/your team.

# New thing to notice here versus last time: in count_active_superusers, you imported both Optional and Iterable. This file only needs Optional — because there's no collection-type parameter here, just a single email string in and a single user (or nothing) out. The imports at the top of a file are a pretty reliable preview of what kind of data the function juggles.

# 3. Signature — every symbol explained
# python
# def get_user_by_email(*, email: str) -> Optional[User]:

# def get_user_by_email
# Defining a function, named after exactly what it gives back — "the user, found by their email."

# (*, email: str)
# The lone * again — your project's keyword-only convention. It means callers must write get_user_by_email(email="a@b.com") and are forbidden from writing get_user_by_email("a@b.com"). With only one parameter here, this might seem unnecessary — what could you possibly mix up with just one argument? But consistency is the actual reason: every service function in your project follows this rule, so nobody has to remember "wait, is this one keyword-only or not?" It's a project-wide habit, not a case-by-case judgment call.

# email: str — a placeholder parameter, type-hinted as a string. No default value, meaning it's mandatory — you cannot call this function without supplying an email.

# -> Optional[User]
# This is the return type hint, and it's an important upgrade over the previous function (get_current_user), which was missing one. This explicitly promises: "you will get back either a User object, or None — nothing else." Anyone calling this function can see, without reading the body, that they need to handle the possibility of None.

# 4. Classes

# No class — same reasoning as the last two functions. This does one self-contained thing (translate an email into a user-or-nothing) with no state to remember between calls. A function is the right, minimal tool.

# 5. Body — line by line

# There's only one line here, but it's doing three things chained together, so we read it as a journey, left to right, one dot at a time — same technique from the "how to read code" lesson.

# python
# return User.objects.filter(email=email).first()

# Step 1 — User
# Start at your User model — the table of all users in the database.

# Step 2 — .objects
# Every Django model automatically gets an .objects manager attached — this is your entry point for querying that model's table. You didn't write this; Django gives it to every model for free.

# Step 3 — .filter(email=email)
# The first verb in the chain: "find rows matching this condition." Inside the parentheses: email=email — left side is the field name on the User model, right side is the parameter you were handed. (Yes, they're spelled the same — Python doesn't get confused, because it knows the left side is a keyword argument name and the right side is your local variable.)

# Important nuance to flag here versus the last two functions you've seen: .filter() doesn't hit the database yet, and it doesn't return one object — it returns a queryset, which could technically match zero, one, or (if your database doesn't enforce email uniqueness) even multiple rows.

# Step 4 — .first()
# The second verb in the chain: "actually run the query now, and give me only the first matching row." Critically: .first() returns None if nothing matched, rather than raising an error. This is the exact behavior that makes the Optional[User] return type hint accurate — .first() is why this function can honestly promise "user or nothing."

# The outer return
# Whatever .first() produces — a User instance or None — gets handed straight back to the caller, no extra processing.

# Whole line, plain English:
# "Look up a user whose email matches the one given; if one exists, return it; if not, return None."

# 6. Beginner questions, answered proactively

# Why .first() instead of .get()?
# This is the single most important design choice in this file, so it's worth its own question. Django's .get() raises User.DoesNotExist if nothing matches, and raises User.MultipleObjectsReturned if more than one row matches. .first() does neither — it just quietly returns None on zero matches, and silently picks one on multiple matches. Given the return type is Optional[User], the author deliberately chose .first() because they want "no user found" to be a normal, expected outcome (someone typing an email that isn't registered) — not an exception-throwing event.

# Why not wrap this in a try/except instead, using .get()?
# You could design it that way — but then every caller would need a try/except User.DoesNotExist block just to handle "not found," which is a very common, non-exceptional case (checking if an email is already registered during signup is a perfectly normal expected "not found"). Using .first() + Optional[User] lets callers use a simple if user is None: check instead of exception handling for something that isn't really an error.

# Why is there no variable here — why not write user = User.objects.filter(...).first() then return user?
# Because user would only be used once, immediately, on the very next line. Storing it in a variable adds a line without adding clarity — this is the opposite situation from get_current_user, where request was reused twice and did earn its own variable. A useful rule of thumb: store something in a variable when you'll refer to it more than once, or when naming it makes a long expression easier to read; otherwise, return the expression directly.

# What if two users somehow share an email?
# .first() would return whichever one the database happens to return first (typically ordered by primary key, unless a default ordering is set on the model), silently ignoring the rest. This function trusts that email uniqueness is enforced elsewhere — likely a unique=True constraint on the email field in your User model — rather than handling that concern itself.

# 7. Design discussion

# Why Optional[User] instead of raising UserNotFoundError or similar?
# This comes back to how the function will actually be used. Think about password reset: you look up a user by the email someone typed into a form. If no account exists, that's not a bug or a crashable error — it's routine, expected input from a real user who might have mistyped, or might be probing whether an email is registered (a case you'd usually want to handle without revealing whether the account exists, for security). A None return lets the caller decide: show a generic "if this email is registered, we sent a code" message either way, rather than branching on a caught exception.

# Trade-off: the cost of this design is that every caller must remember to check for None — nothing forces them to. A function using .get() and raising would force the caller to think about the "not found" case (or crash loudly if they forget), whereas Optional[User] relies on discipline and the type hint alone.

# 8. DIY Recipe — build one like this yourself

# How to build your own "lookup by unique field" function:

# Decide if "not found" is a normal case or an error case for this specific lookup. Login/reset/signup lookups: normal. A lookup where you've already established the record must exist (e.g., "get the target of an action you just verified"): probably an error case instead.
# If it's normal: use .filter(...).first() and hint the return type as Optional[Model].
# If it's an error case: use .get(...) and either let Django's built-in DoesNotExist propagate, or catch it and raise your own more descriptive exception.
# Keep the parameter keyword-only if your project's convention says so, even for a single-argument function — consistency beats "do I really need this here."
# Don't add a variable for a value you use exactly once — return the chained expression directly when nothing is gained by naming it.
# 9. General pattern recognition

# This is the "safe single-record lookup" pattern:

# python
# def get_<thing>_by_<field>(*, <field>: <type>) -> Optional[Model]:
#     return Model.objects.filter(<field>=<field>).first()

# Contrast this with the "guard-check query" pattern from count_active_superusers (filter → conditionally exclude → count) and the "context extraction with fallback" pattern from get_current_user (dig into a nested object → check a condition → return value or None). Three functions, three genuinely different shapes — recognizing which pattern a new function belongs to before you even read the body will speed up how fast you understand new code in this project.

# 10. Real project usage

# This is exactly the kind of function that feeds into your OTP-based password reset flow:

# python
# def request_password_reset(*, email: str) -> None:
#     user = get_user_by_email(email=email)
#     if user is None:
#         # Deliberately do nothing visible — don't reveal whether the email exists
#         return
#     code = create_verification_code(user=user, purpose="password_reset")
#     send_reset_email(user=user, code=code)

# Notice how the None case is handled silently here rather than raising — that's a deliberate security pattern (not confirming or denying account existence to whoever's making the request), and it's only possible because get_user_by_email was designed to return None instead of raising.

# 11. Common beginner mistakes

# ❌ Forgetting to check for None before using the result — e.g., user = get_user_by_email(email=email); user.is_active crashes with AttributeError: 'NoneType' object has no attribute 'is_active' the moment no match is found.

# ❌ Using .get() here instead of .first(), assuming "there should only be one match" is enough justification — forgetting that .get() throws an exception on zero matches, which turns every normal "email not registered" case into a crash unless wrapped in try/except.

# ❌ Case-sensitivity assumptions — filter(email=email) is an exact match by default. If someone signed up with Person@Example.com and later types person@example.com, this won't find them unless the email is normalized (usually lowercased) at signup/lookup time — a very common real-world bug in login systems.

# ❌ Not enforcing uniqueness at the database level and relying on application code to "just not create duplicates" — .first() will mask the problem by quietly returning one of several matches instead of surfacing the data integrity issue.

# 12. Think like the original developer

# If you had to invent this yourself with no reference:

# What problem am I solving? "I keep needing to turn an email into a user object, and I need to decide once, everywhere, what happens when nobody matches."
# What inputs will I need? Just the email string — nothing else is needed to identify a user by this field.
# What could go wrong? No match found (very common, not an error); multiple matches somehow existing (a data-integrity edge case I'll trust the database schema to prevent via a unique constraint).
# How should I report "not found"? Since this will be called from places like login and password reset where "not found" is routine, don't throw an exception — hand back None and document that clearly in the return type hint.
# What should happen if everything works? Return the actual User object, unmodified, so the caller can immediately act on it (check is_active, generate a token, whatever comes next).