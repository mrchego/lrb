import secrets
import string

# 1. The Core Shared Engine (Internal)
def _generate_secure_token(length, character_pool):
    """
    Core engine that leverages secrets to securely pick characters 
    from a specified pool for a given length.
    """
    return ''.join(secrets.choice(character_pool) for _ in range(length))


# 2. The Small Operational Wrappers (Public API)
def generate_random_string(length=32):
    """Generates an alphanumeric secure string."""
    alphabet = string.ascii_letters + string.digits
    return _generate_secure_token(length, alphabet)


def generate_numeric_code(length=6):
    """Generates a secure digits-only numerical pin code."""
    return _generate_secure_token(length, string.digits)


# 1. Purpose (why this exists)

# Sometimes your app needs to create a piece of random-looking text itself — not something the user typed in. Two examples this file handles: a long random string (useful for things like a password-reset token, an API key, a session identifier) and a short random numeric code (like the OTP verification code your project already uses — recall your RBAC project's own VerificationCode model: a 6-digit code with a 5-minute expiry). This file is the shared place that generates both, safely.

# 2. The imports
# python
# import secrets

# A built-in Python toolbox specifically designed for generating cryptographically secure randomness — meaning randomness that's genuinely unpredictable, safe to use for security-sensitive things like passwords, tokens, or verification codes.

# python
# import string

# A built-in Python toolbox holding pre-made collections of common characters — like "every lowercase letter," "every digit," etc. — so you don't have to type them out by hand.

# 3. generate_random_string
# python
# def generate_random_string(length=32):

# One input, length, with a default of 32 — meaning "if nobody says otherwise, generate a 32-character string."

# python
#     alphabet = string.ascii_letters + string.digits
# string.ascii_letters — a ready-made piece of text containing every lowercase and uppercase English letter: "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ".
# string.digits — a ready-made piece of text containing every digit: "0123456789".
# + between two pieces of text (strings) in Python means "glue them together." So alphabet becomes one long string containing every letter (both cases) and every digit — the full pool of characters we're allowed to randomly pick from.
# python
#     return ''.join(secrets.choice(alphabet) for i in range(length))

# This is a dense line — let's take it apart piece by piece, starting from the innermost part:

# range(length) — creates a sequence of numbers counting from 0 up to (but not including) length. If length=32, this gives you 0, 1, 2, ... 31 — 32 numbers total. We don't actually care about the numbers themselves here; we're just using this to say "do the next thing exactly length times."
# secrets.choice(alphabet) — picks one single random character from alphabet, using the secure randomness tool.
# secrets.choice(alphabet) for i in range(length) — this is called a generator expression: "do secrets.choice(alphabet) once for every number in range(length)." Since we loop length times, we get length random characters, one at a time. Note i is never actually used anywhere — same idea as the _ you saw earlier (a value we're forced to have because of how the loop works, but don't care about).
# ''.join(...) — takes all those individual random characters and glues them into one single string, with nothing between them (the empty string '' is what's placed between each piece when joining — here, nothing at all).

# Put together: pick 32 random letters/digits, one at a time, and glue them into one string — e.g., "aZ3kP9mQ...".

# 4. generate_nueric_code
# python
# def generate_nueric_code(length=6) -> str:

# Same shape as before, but notice something new: -> str at the end. This is a return type hint — it's a note (not enforced by Python itself) saying "this function will give back a string." It doesn't change how the function runs; it's purely documentation for humans and tools like IDEs/type-checkers.

# python
#     return ''.join(secrets.choice(string.digits) for _ in range(length))

# Nearly identical to the line above, with two differences:

# Uses string.digits only (just "0123456789") instead of the full letters+digits pool — so this always produces purely numeric output, like "493028".
# Uses _ instead of i for the throwaway loop variable — functionally identical, just a naming choice (and actually the more conventional one, since _ more clearly signals "unused" than i does).

# python
# def _generate_secure_token(length, character_pool):

# You put a leading underscore on this function's name. This is a genuine Python convention worth knowing explicitly: a leading underscore (_generate_secure_token) is a signal — not enforced by Python, just a strong community convention — meaning "this is internal, not meant to be imported or called directly from outside this file." It tells anyone reading your code (or an IDE autocompleting imports) "the public, intended-to-be-used functions are generate_random_string and generate_numeric_code — this one's just plumbing underneath them, don't reach for it directly."

# This is the exact same idea as _ for a throwaway loop variable, just applied to function names instead of variables — a leading underscore always means roughly "ignore this / this isn't meant for you." You picked this up correctly even though I hadn't explicitly taught it yet — good instinct, and worth keeping as a habit: any time you build a "shared engine" function that only your own wrappers should call, prefix it with _.

# DIY — How to Build Your Own Secure Random Generator
# Always use secrets, never random, for anything security-sensitive (tokens, codes, passwords, session IDs). Python's random module is predictable enough to be guessed/attacked in security contexts — secrets exists specifically to avoid that trap. This is a hard rule, not a preference.
# Build your character pool from string's ready-made constants (string.digits, string.ascii_letters, string.punctuation, etc.) rather than typing out character sets by hand — less error-prone, and instantly readable to anyone else.
# Use the ''.join(secrets.choice(pool) for _ in range(length)) pattern as your go-to template for "give me N random characters from this pool."
# Parameterize the length and the pool, so one shared function can serve every specific need (numeric codes, alphanumeric tokens, longer API keys) rather than writing near-duplicate functions each time.
# Double-check function names for typos before they spread — a misspelled function name becomes permanent friction the moment other files start importing it.