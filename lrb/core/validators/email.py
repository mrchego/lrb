from django.core.validators import EmailValidator
from django.core.exceptions import ValidationError

django_email_validator = EmailValidator()

def validate_email(value):
    try:
        django_email_validator(value)
    except ValidationError as e:
        raise ValidationError(e.message)
    return value


# core/validators/email.py (or wherever validate_email lives)
# 1. Purpose (why this exists)

# Same idea as validate_uuid, but for email addresses. Users will type emails into signup forms, invite forms, profile updates — and "text that looks like an email" needs checking before it goes anywhere near your database or your email-sending task from earlier (send_email_task would happily try to send to "not-an-email" and just fail confusingly). This function's job: confirm a piece of text is actually shaped like a real email address before your app trusts it.

# 2. The imports
# python
# from django.core.validators import EmailValidator

# Django ships a ready-made tool specifically for checking if text looks like a valid email — you don't have to write your own email-format-checking logic (which is genuinely tricky to get right — email format rules have a lot of edge cases). EmailValidator is a class (a blueprint), not a function you call directly yet — you have to create an actual instance of it first, which is what the next line does.

# python
# from django.core.exceptions import ValidationError

# Same tool you've already seen in validate_uuid — Django's standard way of saying "this input is invalid."

# 3. Creating the validator — a line outside any function
# python
# django_email_validator = EmailValidator()

# This line runs once, the moment this file is first loaded by Python — not every time validate_email is called. EmailValidator() — the parentheses mean "build me an actual instance of this blueprint." We're storing that ready-to-use instance in a variable named django_email_validator, so validate_email (below) can reuse the same instance every time, instead of rebuilding a new one on every single call. This is a small efficiency choice — building the validator has a tiny bit of setup cost, so doing it once and reusing it is slightly cheaper than doing it fresh inside the function every time.

# 4. The function
# python
# def validate_email(value):

# Same shape as validate_uuid — one function, one input (value, the text to check).

# python
#     try:
#         django_email_validator(value)

# Here's something worth noticing: django_email_validator is a variable holding an object — but we're calling it like a function, with (value). This works because EmailValidator is built in a special way (it defines a __call__ method internally, which is a Python feature letting an object act like a function when you put parentheses after it). You don't need to build this yourself — just know that Django designed it so you use it exactly like calling a function, even though technically it's an object. If value doesn't look like a valid email, this line raises Django's ValidationError internally.

# python
#     except ValidationError as e:

# Same except idea as before — but notice the new part: as e. This means "if this specific type of error happens, catch it, and also give me a name (e) to refer to the actual error object that was raised," so we can look inside it in the next line.

# python
#         raise ValidationError(e.message)

# This is genuinely interesting and worth slowing down on. We caught a ValidationError (named e), and now we're raising a brand new ValidationError — same type as before — but instead of just letting the original one keep going, we're deliberately pulling out just e.message (the specific text explaining what went wrong, e.g., "Enter a valid email address.") and wrapping it in a fresh error.

# Why bother re-raising the same type with just the message? Because Django's built-in EmailValidator might include extra internal details in the original error object (like an error code, e.g., "invalid") that aren't relevant here — this line deliberately strips it down to just the clean, human-readable message, throwing away the rest. It's a "clean up before I hand this along" step.

# python
#     return value

# Same as before — if nothing went wrong, hand back the original value unchanged, signaling success.

# A question worth asking before the DIY guide

# Compare this file to validate_uuid. In validate_uuid, the code catches (ValueError, TypeError) — Python's own built-in error types — because uuid.UUID() is a plain Python tool, not a Django-specific one. Here, EmailValidator is Django's own tool, so naturally it raises Django's own ValidationError directly — no translation needed between two different systems, unlike the UUID decorator bug we just fixed.

# Question for you: given everything we discussed in require_valid_uuid about matching exception types precisely — if you wrote a require_valid_email decorator (mirroring require_valid_uuid), what exact exception type would you need to except around your call to validate_email(value), to avoid making the exact same mismatch bug again?

# DIY — How to Build Your Own "Wrap a Third-Party Validator" Function

# This file is actually a small, reusable pattern — not just "the email checker." Here's the recipe for wrapping any validation tool (Django's, a third-party library's, or your own) into a clean, consistent function:

# Find or build the actual checking tool. Sometimes it's a function (like uuid.UUID), sometimes it's a class you need to instantiate first (like EmailValidator()). If it's a class with reusable setup, create the instance once, outside your function, at the top of the file — not inside the function, where it'd rebuild every call.
# Write a small wrapper function that takes one value. Keep the shape consistent across all your validators in the project: def validate_something(value): — same pattern every time, so anyone reading your codebase instantly recognizes "this is a validator" just from the shape.
# Call the real checking tool inside a try: block.
# Catch the exact exception type the real tool actually raises — not a type you assume it raises. Go check the tool's own documentation or source if you're not 100% sure (this is exactly the mistake that caused the require_valid_uuid bug).
# Decide: do you re-raise the same error type, or translate it into a different one?
# If this validator is meant to be plugged directly into Django (a model field's validators=[...]), keep it raising Django's ValidationError — that's the contract Django expects, as we discussed for validate_uuid.
# If this validator will be called from a GraphQL service directly, you'd want it (or a wrapper around it) to raise your project's AppValidationError instead, so it fits your GraphQL error boundary.
# Always return value at the end on success, so the function can be used inline, like email = validate_email(user_input).

# Following this exact recipe, you could build validate_phone_number, validate_username, validate_postal_code — anything — in minutes, with the same safe shape every time.