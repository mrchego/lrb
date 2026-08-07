from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

def validate_password_strength(password: str) -> None:
    if len(password) < 8:
        raise ValidationError(_("Password must be at least 8 characters long."))
    
# 1. Purpose — What problem does this solve?

# Django lets you attach validators to model fields and forms — small functions that check "is this value acceptable?" before it's saved. Password strength is a perfect example: you don't want to allow "1234" as someone's password anywhere in your RBAC project (signup, password reset, admin-created accounts, etc.).

# This function centralizes the rule "a password must be at least 8 characters" into one reusable place, instead of scattering if len(password) < 8 checks across every form, serializer, and mutation that touches passwords.

# Why not just write the check inline everywhere? Because password rules almost always change over time (add a digit requirement, add a special-character requirement, increase the minimum length). If the rule lives in ten different files, you have to remember to update all ten — and you'll eventually miss one, creating an inconsistent security hole. One function = one source of truth.

# When is this used? Anywhere a password is being set — user signup, password reset via your OTP flow, an admin resetting someone's password, changing your own password. It'd typically be attached to a Django form field's validators=[...] list, called directly inside a service function, or both.

# What breaks without it? Nothing crashes structurally — but there'd be no enforced minimum, meaning users could set a 1-character password, which is a real security vulnerability, especially in an RBAC system where compromised accounts can escalate privileges.

# 2. Imports — explained like you've never programmed
# python
# from django.core.exceptions import ValidationError
# from django.utils.translation import gettext_lazy as _

# django.core — the deepest, most fundamental part of the Django framework — code that almost every other Django feature depends on internally (as opposed to django.contrib, which is optional add-ons like the admin site you saw last time).

# django.core.exceptions — a module specifically holding Django's custom exception types — special classes representing "something went wrong," which Python can raise to interrupt normal execution and signal an error.

# ValidationError — one specific exception class. It's Django's standard way of saying "this piece of data is not valid," and — importantly — Django's forms, model .full_clean(), and DRF serializers all know how to catch this specific exception type and turn it into a user-facing error message automatically. That's why you use this exception instead of, say, Python's generic built-in ValueError — ValidationError plugs directly into Django's validation machinery.

# gettext_lazy as _ — same tool you've now seen twice: marks a string as translatable, deferred until display time, aliased to _ for brevity.

# Why import ValidationError from django.core.exceptions and not write your own custom exception class? Because reinventing your own exception type would mean Django's forms/admin/serializers wouldn't recognize it, and you'd have to manually catch and convert your custom exception everywhere it might occur. Using Django's own ValidationError means this function "speaks the same language" as the rest of the framework, for free.

# 3. Function Signature — every symbol explained
# python
# def validate_password_strength(password: str) -> None:

# def — "I'm defining a reusable action," as before.

# validate_password_strength — the function's name. Following the convention validate_<what> is itself a signal — Django recognizes functions/classes named this way (or rather, developers do, by convention) as validators: something you call to check a value, not something that transforms or returns a value.

# (password: str)

# password — the parameter: a placeholder name for "whatever value gets handed in when this function is called." Nothing is actually being checked yet at this point — this is just declaring "this function expects to receive one thing, and I'll call it password inside the function body."
# : str — a type hint. It's telling any human (or IDE, or type-checker tool) reading this code: "I expect password to be a string." Crucially, Python does not enforce this at runtime — if you called validate_password_strength(12345) (a number, not a string), Python would not stop you; it would try to run len(12345), which would actually error out on its own (int has no len()), just not with a helpful message pointing at the type mismatch. Type hints are documentation/tooling aids, not runtime police.

# -> None

# This is the return type hint, appearing after the closing parenthesis and a -> arrow.
# It says: "this function does not return a meaningful value — its purpose is entirely about a side effect (checking, and possibly raising an error), not about producing a result to use afterward."
# Does this change runtime behavior? No — exactly like : str above, -> None is purely a hint for humans/tools. Python will happily let you return 5 even with -> None declared; it just won't warn you unless you're running a separate static type checker (like mypy).
# Why do people bother writing -> None at all, if Python doesn't enforce it? Because it communicates intent immediately to any reader (and to Django itself, conceptually): "call this for its checking behavior, not to grab a return value." It also lets tools like mypy catch genuine bugs — e.g., if someone accidentally wrote return password deep inside a future edit, a type checker would flag the mismatch against -> None.

# No self, no class — why?
# This is a plain function, not a method inside a class (unlike ready(self) or get_actions(self, request) from your earlier files). It doesn't need self because it isn't tied to any particular object's internal state — it's a pure, standalone utility: give it a string, it either does nothing or raises an error. This is intentional and common for validators — they're typically kept as small, dependency-free functions so they're trivially reusable anywhere (forms, serializers, services, tests) without needing to instantiate any class first.

# 4. Classes

# Not applicable here — there are no classes in this file. Worth noting explicitly why not: this function has no internal state to track between calls, no configuration options that would benefit from being bundled as attributes, and no need for inheritance. It's a pure function — the simplest possible tool for the job. (Contrast this with BaseModelAdmin, which needed to be a class specifically because Django's admin framework requires objects with configurable attributes.)

# 5. Body — line by line
# python
# if len(password) < 8:
#     raise ValidationError(_("Password must be at least 8 characters long."))

# Line 1: if len(password) < 8:

# Reading right side first, inside-out (there's a nested call here):

# Innermost call: len(password) — verb: count. Who's performing it: the built-in len() function. What's it counting: the characters in the string password. This returns a plain integer — e.g., "abc" → 3.
# Comparison: ... < 8 — checks whether that count is strictly less than 8.
# Whole condition, plain English: "Is the password shorter than 8 characters?"

# if / : — if is a keyword meaning "only run the following indented block when this condition evaluates to True." The colon : again marks the start of that indented block, same role as in the class/function definitions you've already seen.

# Line 2: raise ValidationError(_("Password must be at least 8 characters long."))

# Reading inside-out, since there are nested calls:

# Innermost: _("Password must be at least 8 characters long.") — verb: mark as translatable. Input: the literal English message string. Returns a lazily-translatable string object.
# Next layer out: ValidationError(...) — verb: construct. This creates a new ValidationError object, handing it that translatable message as its content/argument. At this point, nothing has "happened" yet — we've only built the error object, we haven't triggered it.
# Outermost: raise ... — verb: stop execution and signal failure. This is what actually interrupts the normal flow of the program and hands the freshly-built ValidationError object up to whatever code called validate_password_strength() in the first place.

# Whole line, plain English: "Immediately halt, and report a validation error with the message 'Password must be at least 8 characters long.'"

# What happens if the password is long enough (8+ characters)?
# Notice: there's no else block, and nothing after the if. If the condition is False, the function simply reaches the end of its body having done nothing — and because of the -> None return type, that's exactly the expected, correct outcome: "no news is good news." The absence of a raised error is the signal that the password passed validation.

# 6. Beginner questions, answered proactively

# Why raise instead of return False?
# This is one of the most important distinctions to internalize as a beginner. return False would just hand back a value — the calling code would have to remember to check if not validate_password_strength(pw): ... every single time, and if anyone forgot that check, invalid passwords would silently slip through. raise forces the problem to be dealt with — execution stops immediately, and unless something explicitly catches (except) the error, it propagates all the way up and becomes visible. It's a much safer default for anything security-related, because forgetting to handle it still fails safely (loudly), rather than silently.

# Why is the whole function just one if, with no try/except?
# Because there's nothing here that can fail unexpectedly — len() on a string is always safe, there's no external system being called (no database, no network), so there's no need to catch any error. The function raises an error on purpose (when the password's invalid); it doesn't need to catch one.

# Why use _(...) around the message at all — isn't the message obviously just English text?
# Because Django's philosophy is "assume this project might need to support other languages someday, even if it doesn't yet." Wrapping every user-facing string in _() from the start costs almost nothing, and makes turning on translations later trivial — you just add translation files, no code changes needed. Skipping it means retrofitting translation support later requires hunting down every raw string in the codebase.

# Why parentheses around password in len(password)?
# Same fundamental reason as your very first file: parentheses are how you hand data into a function. len is a function; whatever's inside its parentheses is the "ingredient" it operates on.

# Why is there no else branch?
# Because "the password is fine" doesn't need an action — it needs the absence of an action. Adding an empty else: pass would be pure noise; Python doesn't require you to explicitly state "and if the condition is false, do nothing" — that's already the default behavior of skipping past an if block.

# 7. Design discussion

# Why choose 8 as a hardcoded number here, rather than reading it from Django settings (e.g. settings.MIN_PASSWORD_LENGTH)?
# Trade-off: hardcoding is simpler and this function has zero external dependencies — you can copy it into any project and it just works. But it means changing the minimum length requires editing code (and redeploying), rather than just changing a config value. For a small learning project, hardcoding is a completely reasonable choice; in a larger production system, you might prefer pulling this from settings so different environments (or even different customer tiers) could configure different password policies without code changes.

# Why check only length, and not complexity (uppercase, digits, symbols)?
# This is likely intentionally minimal — a starting point. Real-world password validators typically check multiple rules, but each rule is usually still just one small, focused conditional like this one — often combined by calling several small validator functions in sequence rather than writing one giant function with many ifs. (Notice this is actually what Django's own built-in password validators do — MinimumLengthValidator, CommonPasswordValidator, NumericPasswordValidator, etc. — several small validators, not one big one.)

# Why a plain function instead of a class-based validator (like Django's own built-in MinimumLengthValidator class)?
# Django's built-in validators are classes because they need to store configuration (e.g. MinimumLengthValidator(min_length=8) — the minimum length is itself configurable per-instance). Since this function hardcodes 8 directly with no configurability, there's no state to store between calls — so a plain function is simpler and sufficient. If you later wanted the minimum length to be configurable per call-site, converting this into a small class (or adding a parameter with a default) would be the natural next step.

# 8. DIY Recipe — build your own validator from scratch
# Decide exactly what you're validating (a password, an email, a UUID, an age).
# Decide the function's signature: one parameter (the value to check), type-hinted for clarity; return type -> None, since validators signal problems by raising, not by returning something.
# Decide the failure condition(s) — write them as if statements checking the "invalid" case (not the "valid" case — it's usually simpler to express "this is wrong" directly than to express "everything about this is right").
# On failure, raise ValidationError(_("A clear, user-facing message")) — always wrap the message in _() for translatability, and make the message specific enough that a user immediately understands what to fix.
# Don't write an else or a "success" return — the function simply finishing without raising is the success case.
# If you need multiple independent rules, prefer writing multiple small validator functions (or classes, if they need configuration) over one large function with many conditions — this mirrors Django's own built-in password validators.

# Following this recipe, you could now write validate_email_format, validate_username_available, validate_age_minimum, etc. — all with the identical shape.

# 9. General pattern recognition

# This is the guard clause / fail-fast pattern: check for the invalid case first, raise immediately if found, and otherwise let execution fall through naturally to an implicit "everything's fine." You'll recognize this same shape constantly — in require_owner()/require_permission() (check "not allowed," raise, otherwise fall through), in view functions that reject bad input early, and in service functions that validate their arguments before doing real work.

# The signal to look for: a function with no else, whose entire body is one or more if <bad condition>: raise ... blocks. That shape is a guard clause validator.

# 10. Real project usage

# Given your RBAC project's structure, this validator would plug in wherever a password is actually set:

# Attached directly to a Django form/serializer field: PasswordField(validators=[validate_password_strength])
# Called explicitly inside a signup or password-reset service function (matching your project's service/selector separation — the service layer is exactly where business-rule validation like this belongs, before the password is hashed and saved)
# Reused in your OTP-based password reset flow, at the exact moment the user submits their new password

# Since your project already separates GraphQL mutations (thin orchestration) from services (business logic), this validator is a business rule — so it belongs called inside a service function like reset_password(*, user, new_password), not inside the GraphQL resolver itself.

# 11. Common beginner mistakes
# ❌ Using return False / return True instead of raise ValidationError(...) — silently allows callers to skip handling invalid input.
# ❌ Forgetting _() around the message string — breaks translation support later.
# ❌ Catching every exception broadly elsewhere in the codebase with a bare except: — this would accidentally swallow this validator's ValidationError along with genuine bugs, hiding real problems.
# ❌ Not converting/checking the input's type before using it (here, assuming password is always a string) — the : str hint doesn't enforce anything at runtime, so a caller passing None would crash inside len(None) with a confusing TypeError, not a clean validation message.
# ❌ Hardcoding the check condition as len(password) <= 8 instead of < 8 — an easy off-by-one mistake that would incorrectly reject exactly-8-character passwords, when the message says "at least 8" should mean 8 is acceptable.
# 12. Think like the original developer
# "I need to make sure passwords meet a minimum standard before they're ever saved."
# "What's the simplest possible rule to start with? Length is the most fundamental one."
# "How do I report 'this is invalid' in a way Django already understands and can automatically surface to a form/user? — Django's own ValidationError is exactly built for that; I shouldn't invent my own error type."
# "What should happen on success? Nothing special — the function just needs to not complain."
# "Will this project ever need multiple languages? Almost certainly eventually — I should wrap user-facing text in _() now, since it costs nothing today and saves rework later."
# "Should this be reusable outside of one specific form? Yes — so I'll keep it as a small, dependency-free function I can import anywhere: forms, serializers, services, tests."

# That reasoning — "smallest possible rule, fail loudly using the framework's own error type, keep it dependency-free and reusable" — is this validator.