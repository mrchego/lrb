from typing import Optional


def get_active_session(*, user_id: str) -> Optional[dict]:
    return {"user_id": user_id, "active": True, "created_at": None}


# 1. Purpose

# This is a selector function — following your project's service/selector split, this is the "read" side (not a "write" service). Its job (in theory) is to look up whether a given user has an active session and return it as data. Right now, though, this function is a stub: it doesn't actually query anything — it just builds and returns a fake dictionary no matter what user_id you pass in. I'll flag that clearly below, because it's important to recognize placeholder code when reading a real project.

# 2. Imports — explained from scratch
# python
# from typing import Optional
# typing is Python's built-in module for type hints — annotations that describe what kind of data a variable, parameter, or return value should be. Type hints don't change how the code runs; Python still runs even if you violate them. They exist for humans and tools (your editor, mypy, etc.) to catch mistakes before running the code.
# Optional is a special type meaning "this value is either the given type, or None." Optional[dict] means "a dict, or None." It's shorthand for Union[dict, None].
# 3. Signature — piece by piece
# python
# def get_active_session(*, user_id: str) -> Optional[dict]:
# def — starts a function definition.
# get_active_session — the function's name. Good naming here: it reads like a sentence describing exactly what it returns.
# (...) — parentheses hold the parameters: fill-in-the-blank placeholders for values the caller must supply.
# * — this is the interesting part. A bare * inside a parameter list is a marker, not a parameter itself. Everything after it must be passed as a keyword argument — name=value — never by position.
# Without it: get_active_session("abc123") would work.
# With it: that call fails. You're forced to write get_active_session(user_id="abc123").
# user_id: str — a parameter named user_id, type-hinted as str (a text string). The : here separates the parameter name from its type hint — it does not mean "the body starts here" (that's a different :, at the very end of the line).
# -> dict (wrapped in Optional[...]) — the return type hint, placed after the closing ) of the parameter list. The arrow -> means "this function returns...". Optional[dict] says: "you'll get either a dict, or None."
# Final : — this one does mean "the indented block below is the function's body."

# Why the forced keyword-only argument? This matches your project's rule: keyword-only arguments on all service/selector functions. The benefit: at the call site, you always see get_active_session(user_id="abc123") — self-documenting, and impossible to accidentally swap argument order if the function later grows a second parameter (e.g., get_active_session(user_id=..., include_expired=...) — position-based calls would silently break if the parameter order ever changed; keyword-only calls never do).

# 4. Body — step by step
# python
#     return {"user_id": user_id, "active": True, "created_at": None}
# {...} — curly braces here build a dictionary literal: a set of key: value pairs. {"user_id": user_id, ...} — the left side of each pair ("user_id") is a fixed string key; the right side is the value stored under that key.
# Note the difference between "user_id" (a string, the key — always in quotes) and user_id (no quotes — the variable, i.e., whatever was passed into the function). Same word, two completely different roles depending on whether it's quoted.
# "active": True — hardcoded to True no matter what. True is Python's boolean literal (capital T, not true).
# "created_at": None — hardcoded to None (Python's "nothing/empty" value) no matter what.
# return — hands this dictionary back to whatever called the function, and immediately exits.

# The stub problem: a real implementation would need to actually look something up — e.g., query a Session model or check a cache — using user_id to find whether a session exists at all. As written, this function will claim every user has an active session, even ones that were never logged in. It also never returns None, despite Optional[dict] promising that it might. This is a strong signal you're looking at scaffolding — a placeholder written to satisfy a function signature (maybe for a GraphQL resolver to call during early development) before the real database query was implemented.

# 5. Why this approach
# Keyword-only params — consistency and safety, as explained above; matches the project-wide convention rather than being special to this function.
# Optional[dict] return type — tells any caller "you must handle the case where this returns None" (e.g., "no active session found"), even though the current body never actually produces that case. The type hint documents the intended contract, ahead of the real logic being written.
# Separate selector function at all — even as a stub, isolating "get the session" into its own function means the caller (a GraphQL resolver, a service, middleware) doesn't need to know or care how the lookup happens. Later, you can swap the stub body for a real database query and every caller keeps working unchanged.
# 6. Connections
# Input: a user_id string — likely pulled from a request's session cookie or an authenticated user object.
# Output: currently, always a dict with active: True. Once implemented, this would come from querying wherever sessions are stored (a Session model, Django's session backend, or Redis).
# Likely caller: middleware or a resolver that needs to check "is this user actually logged in / does their session still count" before allowing an action — this smells like part of your auth flow (your project uses session/cookie-based auth).
# 7. Advanced concepts

# Keyword-only arguments (*) in depth — Python parameter lists can have up to three sections, in order:

# python
# def f(positional, *, keyword_only):

# Anything before a bare * can be passed positionally or by keyword. Anything after * can only be passed by keyword. Here, there's nothing before the *, so every parameter (just user_id) is keyword-only — no positional calling allowed at all.

# Optional[X] vs just X — a function typed to return dict promises a dict, always. A function typed Optional[dict] is telling every caller: "check for None before you use this." This is a real correctness signal in bigger codebases — if you see Optional, you know downstream code needs a None-guard (if session is None: ...) or it will crash on None.something.

# 8. Small example
# python
# def get_user_age(*, name: str) -> Optional[int]:
#     ages = {"amina": 30}
#     return ages.get(name)  # returns None if name isn't in the dict

# get_user_age(name="amina")   # 30
# get_user_age(name="kevin")   # None
# get_user_age("amina")        # TypeError — must use keyword!

# This shows what get_active_session should eventually look like: a real lookup that can genuinely return None, not a hardcoded value.

# 9. What to remember
# A bare * in a parameter list forces everything after it to be keyword-only — no positional calls allowed.
# key: value inside {} builds a dict — the key is always a literal (usually a quoted string), the value can be any expression, including a variable that happens to share the key's name.
# Type hints are promises, not enforcement — -> Optional[dict] doesn't make the function sometimes return None; the code has to actually do that. Read type hints as "what this function is supposed to do," then verify the body actually does it.
# Recognize stub/placeholder code — a function that ignores its input and returns a hardcoded value is a strong signal it's scaffolding, not a finished implementation. Don't assume every function you read in a real project is "done."
# Separating lookup logic into its own function pays off even before it's finished — callers can be written against the function's signature while the real implementation is filled in later.