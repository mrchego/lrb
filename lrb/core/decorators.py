from functools import wraps
from django.core.exceptions import ValidationError
from lrb.core.exceptions import AppValidationError
from lrb.core.validators.uuid import validate_uuid


def require_valid_uuid(field_name='id'):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            value = kwargs.get(field_name)
            if value:
                try:
                    validate_uuid(value)
                except ValidationError:
                    raise AppValidationError(f"Invalid {field_name} format.")
            return func(*args, **kwargs)
        return wrapper
    return decorator

# 1. Purpose (why this exists)

# Lots of your GraphQL mutations/resolvers accept an id (or company_id, role_id, etc.) as an argument, and that ID needs to be a real, valid UUID before you do anything else with it — otherwise you'll hit a confusing database error later instead of a clean "invalid input" message right away. Rather than writing the same "check this ID is a valid UUID" code at the top of every single function that needs it, this file creates a reusable stamp you can slap on top of any function: "before you run, automatically check this one argument is a valid UUID for me."

# This is a decorator — a wrapper that adds behavior around a function without changing the function's own code.

# 2. The imports
# python
# from functools import wraps

# functools is a built-in Python toolbox for working with functions themselves. wraps is one specific tool from it — we'll see exactly what it does below, but the short version: it helps a wrapped function still "look like" the original function to things like debuggers and documentation tools.

# python
# from lrb.core.exceptions import AppValidationError

# Brings in the custom error type we studied in exceptions.py — the one meant to represent "the input was invalid."

# python
# from lrb.core.validators.uuid import validate_uuid

# Brings in the UUID-checking function we studied earlier.

# 3. The three nested functions — this is the tricky part, so slowly

# Decorators in Python almost always look like "a function, containing a function, containing a function." Let's peel it apart layer by layer.

# Layer 1 — the outermost function
# python
# def require_valid_uuid(field_name='id'):

# This is the function you actually call by name when using this decorator, like:

# python
# @require_valid_uuid(field_name='company_id')
# def some_resolver(...):
#     ...
# field_name='id' — an input with a default. This lets you customize which argument name to check — most of the time it might be called id, but sometimes it's company_id or role_id, so this makes the decorator reusable for any of them.

# This function's entire job is to remember field_name, and then hand back the next layer down.

# Layer 2 — the actual decorator
# python
#     def decorator(func):

# This inner function is defined inside require_valid_uuid, so it automatically has access to field_name from outside it (this is called a "closure" — an inner function remembering variables from the function that contains it, even after the outer one has finished running).

# func — this represents whatever function you're decorating — e.g., your actual resolver, some_resolver, gets passed in here automatically by Python when you use the @ syntax.

# This function's job: take the real function (func), and hand back a new, wrapped version of it.

# Layer 3 — the wrapper (this is what actually runs)
# python
#         @wraps(func)
#         def wrapper(*args, **kwargs):
# @wraps(func) — this is the functools tool from earlier. Without it, the wrapped function would lose its original name/docstring (Python would think the function is literally named wrapper everywhere, which is confusing in error messages, debugging tools, or Django's introspection). @wraps(func) copies over the original function's identity so it still looks like itself from the outside.
# def wrapper(*args, **kwargs): — this is the function that actually replaces your original resolver. *args catches any extra positional inputs, and **kwargs catches any inputs given by name (like id="some-uuid-string"). Together, this means: "no matter what inputs the original function normally takes, I'll accept all of them here too, without needing to know exactly what they are in advance."
# python
#             value = kwargs.get(field_name)

# kwargs is a dictionary (a collection of name: value pairs) of every named input given to the function. .get(field_name) looks up the one whose name matches whatever field_name was set to (e.g., "id"), and gets its value — or None if it wasn't provided at all.

# python
#             if value:

# Only bother checking if something was actually given (skips the whole check if value is None/empty).

# python
#                 try:
#                     validate_uuid(value)
#                 except AppValidationError:
#                     raise AppValidationError(f"Invalid {field_name} format.")

# Attempts to validate the UUID. If it fails, catches the problem and re-raises a new AppValidationError, with a message that includes which field was bad (using an f-string — f"..." lets you drop a variable like {field_name} directly into a piece of text).

# python
#             return func(*args, **kwargs)

# If we got this far, the UUID was fine (or wasn't given at all) — so now actually call the real, original function (func), passing along all the same inputs it originally received, and hand back whatever it returns.

# python
#         return wrapper
#     return decorator

# Each outer layer hands back the layer it built, so the whole chain connects properly when Python processes the @require_valid_uuid(...) syntax above a function.

# Something important I need to flag — a real bug

# Look very closely at this part:

# python
# try:
#     validate_uuid(value)
# except AppValidationError:
#     raise AppValidationError(f"Invalid {field_name} format.")

# Go back to validators.py — do you remember what validate_uuid actually raises when the UUID is invalid? It was Django's own django.core.exceptions.ValidationError — not AppValidationError.

# How to Build Your Own Decorator — A Reusable Guide

# Since you've now seen one real decorator (require_valid_uuid), here's the general recipe so you can build new ones yourself, any time you need one.

# Step 1 — Ask: what is this decorator actually for?

# A decorator is for behavior you want to run before or after a function, without touching that function's own code. Ask yourself: "what do I want to check, log, time, or block — automatically — every time this function runs?"

# Examples of things decorators are good for in your project:

# Checking permissions before a mutation runs (@require_permission("edit_role"))
# Validating an input before the real logic runs (like require_valid_uuid)
# Wrapping something in a database transaction automatically
# Logging how long a function took to run
# Making sure a user is logged in before a resolver runs
# Step 2 — Does it need settings, or not?

# This is the first real decision, and it determines your whole shape.

# Question to ask: "Will I ever need to customize this decorator when I use it?" (e.g., require_valid_uuid(field_name='company_id') — customizing which field to check)

# If NO customization needed (it always does the exact same thing every time) → you only need two layers:
# python
# def my_decorator(func):
#     @wraps(func)
#     def wrapper(*args, **kwargs):
#         # your logic here
#         return func(*args, **kwargs)
#     return wrapper

# Used like: @my_decorator (no parentheses, no arguments).

# If YES, customization needed (like choosing a field name, a permission code, a number of retries) → you need three layers, exactly like require_valid_uuid:
# python
# def my_decorator(some_setting):
#     def decorator(func):
#         @wraps(func)
#         def wrapper(*args, **kwargs):
#             # your logic here, using some_setting
#             return func(*args, **kwargs)
#         return wrapper
#     return decorator

# Used like: @my_decorator(some_setting="value") (with parentheses, because you're actually calling the outer function first).

# This is the single most important rule to remember: count how many parentheses show up when you use the decorator. Zero settings needed → two layers. Any settings needed → three layers.

# Step 3 — Always include these two things, no matter what
# @wraps(func) right above your wrapper function — always, every time. This is a "just do it" rule; skipping it causes debugging confusion later (the wrapped function loses its real name).
# *args, **kwargs in your wrapper's signature, and pass them along unchanged when you call func(*args, **kwargs) at the end — unless you have a specific reason to change what gets passed through. This makes your decorator work on any function, regardless of what inputs it takes.
# Step 4 — Decide: does your logic run before, after, or both?
# Before only (like require_valid_uuid — check something, maybe stop early): put your logic before the return func(*args, **kwargs) line, and use raise to stop early if something's wrong.
# After only (like logging "the function finished"): call func(*args, **kwargs) first, save its result in a variable, run your logic, then return the saved result.
# Both (like timing how long something took): do something before, call func(...), then do something after, using the time difference.
# python
# def timed(func):
#     @wraps(func)
#     def wrapper(*args, **kwargs):
#         start = time.time()          # before
#         result = func(*args, **kwargs)
#         elapsed = time.time() - start  # after
#         print(f"{func.__name__} took {elapsed}s")
#         return result
#     return wrapper
# Step 5 — Watch for the exact bug we just found

# Whatever function you call inside your decorator, double-check which exact error type it actually raises, and catch that same type — not a similar-sounding one. This is exactly the mistake in require_valid_uuid: it caught AppValidationError, but validate_uuid actually raises Django's ValidationError. Always trace back to the source function and confirm the real exception type before writing your except.

# Quick checklist for every new decorator you write
# Does it need settings when used? → decide 2-layer vs 3-layer shape
# Add @wraps(func) above your wrapper — always
# Use *args, **kwargs in the wrapper, pass them through unchanged
# Decide: logic before func(...), after, or both
# If catching an error, verify the exact type the inner function actually raises