import re
from django.core.exceptions import ValidationError
from lrb.core.constants import PHONE_REGEX


def validate_phone_number(value):
    if not re.match(PHONE_REGEX, value):
        raise ValidationError("Enter a valid phone number.")
    return value

# PHONE_REGEX = r"^\+?1?\d{9,15}$"
# Two files here — constants.py (the regex) and validators/phone.py (the check)
# 1. Purpose (why this exists)

# Same family as validate_email and validate_uuid — before your app trusts a "phone number" a user typed in, it needs to confirm the text is actually shaped like a real phone number (not "abc", not empty, not a sentence). This one's different from the others though: there's no built-in Django tool for phone numbers (unlike EmailValidator), so this file builds the check itself using a regex — a pattern-matching tool for text.

# 2. The constant
# python
# PHONE_REGEX = r"^\+?1?\d{9,15}$"

# This lives in constants.py, alongside DEFAULT_PAGE_SIZE and the others — same reasoning as always: one canonical definition of "what a valid phone number looks like," so every file that needs to check a phone number references this one pattern instead of each inventing (and possibly slightly mismatching) their own.

# What is a regex, in plain terms? A regex ("regular expression") is a tiny, specialized mini-language for describing "what shape of text am I looking for" — instead of writing a bunch of manual if checks (is it long enough? does it start with a digit or a plus sign? are there only numbers?), you write one compact pattern, and a matching engine checks if a given piece of text fits that pattern.

# Let's decode this specific pattern, symbol by symbol:

# r"..." — the r before the quotes means "raw string." Normally in Python, \d inside a regular string can get misinterpreted as an escape sequence. r"..." tells Python "don't process backslashes specially, hand this text to the regex engine exactly as typed." Always use r"..." for regex patterns — it's a "just do it" rule, like @wraps(func) was for decorators.
# ^ — means "the match must start right here, at the very beginning of the text." Without it, the pattern could match somewhere in the middle of a longer string and still count as valid — ^ prevents that.
# \+? — \+ means "a literal plus sign character" (the backslash is needed because + normally means something else in regex — more below). The ? right after means "this previous thing is optional — zero or one of it." So together: "there might be a + at the start, or there might not be."
# 1? — same ? idea: "there might be a literal 1 here (common for U.S. country code), or there might not be."
# \d{9,15} — \d means "any single digit, 0 through 9." {9,15} means "repeat the previous thing somewhere between 9 and 15 times." So together: "9 to 15 digits in a row."
# $ — means "the match must end right here, at the very end of the text." Paired with ^ at the start, this ensures the entire string matches the pattern from start to finish — not just some portion of it.

# Put together, in plain English: "optionally starts with a +, optionally followed by a 1, then 9 to 15 digits, and nothing else before or after."

# 3. The imports
# python
# import re

# re is Python's built-in toolbox for working with regexes — the actual engine that takes a pattern like PHONE_REGEX and checks it against real text.

# python
# from lrb.core.constants import PHONE_REGEX

# Grabs the shared pattern we just decoded.

# python
# from lrb.core.exceptions import AppValidationError

# This time — notice — it imports your project's own AppValidationError directly, not Django's ValidationError like validate_uuid and validate_email did. Worth flagging as a real, deliberate difference (touched on more below).

# 4. The function
# python
# def validate_phone_number(value):

# Same one-input shape as your other validators.

# python
#     if not re.match(PHONE_REGEX, value):
# re.match(PHONE_REGEX, value) — asks the re toolbox: "does value match this pattern?" If it matches, this returns a special "match object" (which Python treats as truthy); if it doesn't match, it returns None (falsy).
# not in front flips that — so this whole line reads: "if value does not match the phone pattern..."
# python
#         raise AppValidationError("Enter a valid phone number.", field="phone")

# If the phone number doesn't match, immediately raise your project's own error type, with a clear message and — notice — the field="phone" argument filled in, so a frontend form knows exactly which input box to highlight red. Recall from exceptions.py: AppValidationError's __init__ takes (message, field=None) — this is exactly using that shape correctly.

# python
#     return value

# Success case — hand back the phone number unchanged, consistent with the "always return on success" rule we just enforced on the image validators.
# DIY — How to Build Your Own Regex-Based Validator

# For any future "check this text matches a specific shape" need (postal codes, usernames, product SKUs, hex color codes):

# Write the pattern as a named constant in constants.py — never inline the raw regex string inside the function itself, for the same single-source-of-truth reasons as everything else in this project.
# Always prefix the pattern string with r (raw string) — non-negotiable, avoids subtle backslash bugs.
# Anchor your pattern with ^ and $ unless you deliberately want a partial match somewhere inside a larger string. Forgetting these is a very common regex mistake — without them, "call me at 5551234567 maybe" could accidentally "match" if a valid phone-shaped substring exists anywhere inside it.
# Use re.match(PATTERN, value) inside an if not ...: check, exactly like this file — that's the standard shape for "does this text match this pattern."
# Decide deliberately which exception type to raise — and make that choice consistent with how similar validators in your project behave, not arbitrary per-file. This is the real lesson from the design question above.
# Always return value on success.