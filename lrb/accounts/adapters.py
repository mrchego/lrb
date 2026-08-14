from __future__ import annotations
import typing
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings

if typing.TYPE_CHECKING:
    from allauth.socialaccount.models import SocialLogin
    from django.http import HttpRequest
    from lrb.accounts.models import User


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request: HttpRequest) -> bool:
        return getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True)


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(
        self,
        request: HttpRequest,
        sociallogin: SocialLogin,
    ) -> bool:
        return getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True)

    def populate_user(
        self,
        request: HttpRequest,
        sociallogin: SocialLogin,
        data: dict[str, typing.Any],
    ) -> User:
        user = super().populate_user(request, sociallogin, data)

        if not user.first_name:
            user.first_name = data.get("first_name", "")

        if not user.last_name:
            user.last_name = data.get("last_name", "")

        return user
    
    
# New concepts here: from __future__ import annotations, the adapter pattern (a bigger structural idea than anything so far), getattr() with a default, and overriding a method that itself calls super() and then modifies the result — similar in shape to get_readonly_fields() from your admin file, but on brand-new territory (social login data).

# 1. Purpose — What problem does this solve?

# django-allauth (the third-party package from your forms file) controls the entire signup/login flow — but it needs to remain generic, since thousands of different projects use it, each with different rules about who's allowed to sign up, and different custom User fields to populate.

# Rather than making you fork or hack allauth's internals, allauth exposes adapters — designated "customization points" you're meant to subclass. This file customizes two specific behaviors:

# Whether registration is currently open at all — for both normal (email/password) signup and social (Google/GitHub/etc.) signup.
# How a User gets its first_name/last_name populated when someone signs up via a social provider — e.g., pulling the name Google already knows about them, into your own User fields.

# Why not just hardcode "signup closed" logic into a view somewhere? Because allauth owns the actual signup views and flow — your project doesn't write its own signup view from scratch. The only way to influence allauth's behavior without rewriting the whole flow yourself is to plug into the exact extension points it deliberately provides: adapters.

# When is this used? AccountAdapter.is_open_for_signup() — every time someone visits your standard email/password signup page. SocialAccountAdapter.is_open_for_signup() / populate_user() — every time someone signs up or logs in via a social provider (e.g., "Continue with Google").

# What breaks without it? allauth's default adapters would be used instead — which, for is_open_for_signup, always return True (registration always allowed, with no way to toggle it off via your settings), and for populate_user, would only use whatever generic logic allauth ships with, not necessarily mapping cleanly onto your specific User model's first_name/last_name fields.

# 2. Imports — explained like you've never programmed
# python
# from __future__ import annotations
# import typing
# from allauth.account.adapter import DefaultAccountAdapter
# from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
# from django.conf import settings

# from __future__ import annotations — this is genuinely unusual syntax, worth pausing on. __future__ is a special, real Python module used specifically to opt early into a language behavior that will (or did) become standard in a later Python version. This particular one changes how Python treats type hints (the : str, -> None annotations you've seen throughout): normally, when Python loads a file, it actually evaluates each type hint as real code at that moment. With this import active, type hints are instead treated as plain, unevaluated text — read only if some tool (like mypy) later decides to inspect them.

# Why does that matter here specifically? Look at the imports guarded under TYPE_CHECKING below — SocialLogin, HttpRequest, User are only really imported when type-checking, not at runtime. Without from __future__ import annotations, writing def populate_user(self, ..., data: dict[str, typing.Any]) -> User: would try to actually evaluate User as a real, existing name the moment Python loads this file — but User was never truly imported at runtime (only inside the skipped TYPE_CHECKING block)! That would crash with a NameError. This future-import defers evaluation of all annotations to "just text, don't check yet," letting you freely reference types like User in hints even though they're never actually imported when the program runs.

# import typing — this time, instead of from typing import TYPE_CHECKING (like the manager file), the whole module is imported. This lets the file use typing.TYPE_CHECKING and typing.Any (used further down) both from the same import, rather than importing each piece individually.

# allauth.account.adapter → DefaultAccountAdapter — allauth's own base class for standard signup/login behavior. This is the class you're about to extend.

# allauth.socialaccount.adapter → DefaultSocialAccountAdapter — allauth's own base class specifically for social login behavior (Google, GitHub, etc.) — a separate adapter from the standard one, mirroring the same "account" vs. "socialaccount" split you saw with the two different SignupForm classes in the forms file.

# django.conf → settings — same settings-access tool as the context processor file.

# python
# if typing.TYPE_CHECKING:
#     from allauth.socialaccount.models import SocialLogin
#     from django.http import HttpRequest
#     from lrb.accounts.models import User

# Same pattern you already learned in the UserManager file: these three imports never actually run when the program executes — they exist purely so type-checking tools can resolve what SocialLogin, HttpRequest, and User refer to in the annotations below. from __future__ import annotations (explained above) is precisely what makes it safe to reference these names in signatures without a NameError, even though they're not "really" imported at runtime.

# Why guard these three specifically, instead of just importing them normally at the top? Likely a mix of two things: avoiding potential circular imports (lrb.accounts.models importing something that eventually imports back into this adapters file), and simply avoiding unnecessary runtime imports for names that are only ever used inside type hints, never actually called or instantiated in the function bodies themselves.

# 3. AccountAdapter — signature and body
# python
# class AccountAdapter(DefaultAccountAdapter):
#     def is_open_for_signup(self, request: HttpRequest) -> bool:
#         return getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True)

# Class signature: class AccountAdapter(DefaultAccountAdapter): — the now-familiar inheritance pattern. This class is a specialized version of allauth's own default account adapter.

# Method signature: def is_open_for_signup(self, request: HttpRequest) -> bool:

# is_open_for_signup — not an arbitrary name — this is a method allauth's DefaultAccountAdapter already defines, and allauth's own signup view specifically calls this exact method by this exact name to decide whether to allow a new signup to proceed. We're overriding it, same concept as get_readonly_fields/get_actions from the admin file.
# request: HttpRequest — the incoming request, type-hinted as Django's HttpRequest class (only resolvable thanks to the TYPE_CHECKING import + from __future__ import annotations combo above).
# -> bool — this method must return True or False — allauth's signup view directly checks this return value to decide whether to show the signup form or reject the request.

# Body: return getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True)

# getattr(object, "name", default) — a Python built-in function: "look up the attribute called "name" on object. If it exists, return its value. If it doesn't exist, don't crash — just return default instead."
# Applied here: "look up settings.ACCOUNT_ALLOW_REGISTRATION. If that setting has been defined in settings.py, use its value. If it hasn't been defined at all, assume True (registration allowed) rather than crashing."
# Why not just write settings.ACCOUNT_ALLOW_REGISTRATION directly, the way the context processor file did? This is a meaningful difference worth noticing between the two files: the context processor file assumed the setting definitely exists (accessing it directly would crash with an AttributeError if it didn't). This adapter is more defensive — using getattr(..., True) means even if someone forgets to define ACCOUNT_ALLOW_REGISTRATION in settings.py at all, the site still works correctly (defaulting to "signup allowed") instead of throwing a server error the moment someone visits the signup page.

# Whole method, plain English: "When allauth asks whether standard signup is currently open, answer based on the ACCOUNT_ALLOW_REGISTRATION setting — defaulting to 'yes, open' if that setting was never configured."

# 4. SocialAccountAdapter.is_open_for_signup — the same idea, different signature shape
# python
# class SocialAccountAdapter(DefaultSocialAccountAdapter):
#     def is_open_for_signup(
#         self,
#         request: HttpRequest,
#         sociallogin: SocialLogin,
#     ) -> bool:
#         return getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True)

# Class signature: same inheritance pattern, this time extending allauth's social-specific default adapter.

# Method signature: notice this version of is_open_for_signup takes one extra parameter compared to the account adapter's version: sociallogin: SocialLogin. This is because allauth defines this method's exact required shape separately per adapter — the social adapter's version needs to know not just "is signup open in general," but has access to the specific in-progress social login attempt (which provider, what data came back from it), in case a real implementation wanted to make that decision conditional on which provider someone's signing up through. This implementation doesn't use sociallogin for anything — it applies the same blanket rule regardless — but the parameter still has to be accepted, because that's the shape allauth's own base class defines and calls with.

# Body: identical logic to the account adapter's version — same getattr(...) call, same setting, same default.

# Why is the exact same three-line body written out twice, in two different classes, instead of sharing it somehow? This is worth sitting with as a real design question (raised properly in the design section below) — it's a bit of duplication that a more DRY-conscious version might avoid.

# 5. populate_user — line by line (the most involved method in this file)
# python
# def populate_user(
#     self,
#     request: HttpRequest,
#     sociallogin: SocialLogin,
#     data: dict[str, typing.Any],
# ) -> User:
#     user = super().populate_user(request, sociallogin, data)

#     if not user.first_name:
#         user.first_name = data.get("first_name", "")

#     if not user.last_name:
#         user.last_name = data.get("last_name", "")

#     return user

# Signature, piece by piece:

# populate_user — again, not arbitrary — this is a method allauth's DefaultSocialAccountAdapter already defines and calls automatically during social signup, specifically to build/fill out a new (not-yet-saved) User instance from the data a social provider handed back.
# data: dict[str, typing.Any] — a dictionary where every key is a string, and every value can be typing.Any — meaning "any type at all, I'm not constraining it." This is used because the data coming back from different social providers (Google vs. GitHub vs. Facebook) varies widely — it might contain "first_name", "email", "picture", and dozens of other possible fields depending on the provider, so there's no single fixed shape to type precisely.
# -> User — this method is expected to return an actual User instance (only resolvable as a type hint thanks to the TYPE_CHECKING + __future__ combo again).

# Line 1: user = super().populate_user(request, sociallogin, data)

# Same super() pattern as get_readonly_fields() from your admin file: "run the parent class's original version of this method first, and use whatever it returns as my starting point."
# allauth's default populate_user() already does a fair amount of generic work — mapping common social-provider fields onto a new User instance's standard fields, as best it can generically.
# Whole line: "Let allauth build the user object using its own default logic first — I'll only adjust specific pieces afterward."
# Why call super() instead of building the whole User from scratch here? Same reasoning as the admin file: allauth's default logic already correctly handles many providers' quirks and edge cases; reimplementing all of that yourself would be redundant and risk missing something allauth already gets right. You're only adding a small, targeted improvement on top.

# Lines 3-4:

# python
# if not user.first_name:
#     user.first_name = data.get("first_name", "")
# not user.first_name — True when first_name is empty/falsy (same "falsy empty string" logic you saw with if not email: in the manager file).
# data.get("first_name", "") — a dictionary method: "look up the key "first_name" in data. If present, return its value. If missing, return "" (empty string) instead of crashing." This is the dictionary equivalent of the getattr(..., default) pattern you just saw two methods above — same defensive idea, different data structure.
# Whole lines: "If allauth's default logic didn't already manage to fill in a first name, try pulling one from the raw social-provider data instead; if that's not there either, fall back to an empty string."

# Lines 6-7: identical logic, for last_name.

# Why check if not user.first_name: first, instead of always overwriting from data? This is a deliberate "don't override what's already correct" guard. super().populate_user() may have already successfully set first_name from its own generic handling — overwriting it unconditionally could actually replace a correctly-populated value with something worse (or blank), if data happens to structure the name differently than allauth's default expects. Checking if not user.first_name means: "only step in and try harder if the default logic came up empty."

# Line 9: return user — hand back the (possibly slightly improved) User instance to allauth, which will proceed to actually save it as part of finishing the social signup flow.

# Whole method, plain English: "Let allauth build the user from social login data using its normal logic. If it didn't manage to fill in a first or last name, try pulling those directly from the raw provider data as a fallback. Either way, return the finished (still unsaved) user object."

# 6. Beginner questions, answered proactively

# Why dict[str, typing.Any] instead of just dict? Both work as type hints, but dict[str, typing.Any] is more informative — it tells a reader (and tooling) "keys are strings, values could be anything," rather than leaving the dictionary's shape completely unspecified. It's a small extra bit of documentation, at no runtime cost.

# Why does is_open_for_signup take different parameters in the two classes, if they're conceptually "the same check"? Because they're overriding two genuinely different parent methods, defined separately by allauth on two separate base classes (DefaultAccountAdapter vs DefaultSocialAccountAdapter) — each parent method's signature was designed for its own specific signup flow, which happens to need different context (a social login attempt exists in one flow, not the other). You must match whatever signature the specific parent method you're overriding actually expects, even if the logic you write ends up being identical.

# Why isn't sociallogin used anywhere in the method body, if it's a required parameter? Exactly the same reasoning as the unused request parameter in your context processor file — Python requires you to accept whatever parameters the method's contract demands, even if your particular implementation doesn't end up needing all of them.

# Is getattr(settings, "X", True) fundamentally different from data.get("X", "")? No — conceptually they're the exact same pattern, just applied to two different kinds of objects: getattr() is for reading an attribute off any Python object (here, the settings object); .get() is a method specifically belonging to dictionaries. Both express "try to read this value, and don't crash if it's missing — use a sensible default instead."

# 7. Design discussion

# Why duplicate the exact same getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True) line in two different classes, instead of extracting it into one shared helper function? This is a genuine, worthwhile design critique. A cleaner version might pull this into a small shared function — e.g., def _registration_allowed() -> bool: return getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True) — and have both adapters call it, so the rule only exists in one place (echoing the exact same "one source of truth" reasoning you saw behind _create_user in the manager file). As written, if this rule ever needed to change (say, adding a check like "also require email verification setting"), a developer would have to remember to update it in two separate classes — a real risk of the two definitions silently drifting apart over time.

# Why defensive getattr(..., True) here, but the context processor file accessed settings.ACCOUNT_ALLOW_REGISTRATION directly with no default? This inconsistency is worth flagging as something to reconcile in your actual project: either the setting is guaranteed to always be defined (in which case the context processor's direct access is fine, and this file's extra defensiveness is unnecessary caution) — or it's not guaranteed (in which case the context processor file is one missing setting away from crashing template rendering project-wide, and should probably adopt the same defensive getattr pattern this file uses). Worth checking your settings.py to confirm ACCOUNT_ALLOW_REGISTRATION is always explicitly set, and picking one consistent approach.

# Why check if not user.first_name rather than always trusting data as the authoritative source? Trade-off between "trust the framework's own logic" and "trust the raw provider data directly." Deferring to super() first, and only falling back to raw data when needed, keeps you aligned with however allauth evolves its own default field-mapping logic over time — you're only patching the gaps, not replacing the whole mechanism.

# 8. DIY Recipe — building your own allauth adapter customization
# Identify which specific allauth behavior you need to change (signup gating, field population, email handling, etc.).
# Find the specific method name on allauth's relevant default adapter class that controls it (check allauth's source/docs — the method name and signature are not something you invent, they're a contract you must match exactly).
# Subclass the appropriate default adapter (DefaultAccountAdapter for standard flows, DefaultSocialAccountAdapter for social flows).
# Override that method, matching its exact parameter list and return type.
# If the override needs to modify, not replace, existing behavior — call super().<method>(...) first, and adjust the result afterward (as populate_user does here), rather than reimplementing everything from scratch.
# For any external setting your override depends on, prefer getattr(settings, "NAME", sensible_default) over direct attribute access, unless you're certain the setting will always be defined.
# Register your adapter classes in settings.py (ACCOUNT_ADAPTER / SOCIALACCOUNT_ADAPTER), or — just like the empty signup form classes — allauth won't know to use them at all.
# 9. General pattern recognition

# This is the Adapter pattern (literally named after the technique here) — a class that sits between your project and a third-party system, translating/customizing the third-party system's generic behavior to fit your specific needs, without modifying the third-party code itself. You'll see this exact shape recur anywhere a framework/package deliberately exposes "override this class/method to customize behavior" hooks — you've already effectively seen smaller instances of the same idea in BaseModelAdmin's get_actions() override and the empty UserSignupForm(SignupForm): pass.

# The narrower, recurring pattern inside this file specifically: super() first, conditionally patch gaps second — call the parent's version to get a reasonable starting result, then selectively fill in only what's missing, rather than either fully trusting the parent or fully ignoring it.

# 10. Real project usage

# AccountAdapter and SocialAccountAdapter get registered in your project's settings.py:

# python
# ACCOUNT_ADAPTER = "lrb.accounts.adapters.AccountAdapter"
# SOCIALACCOUNT_ADAPTER = "lrb.accounts.adapters.SocialAccountAdapter"

# From that point on, every time allauth's own internal views need to check "is signup allowed?" or "build a user from social provider data," it calls into your classes instead of its own defaults — tying directly back to the same ACCOUNT_ALLOW_REGISTRATION setting your context processor file exposed to templates, and connecting to the first_name/last_name fields you saw defined on your User model.

# 11. Common beginner mistakes
# ❌ Overriding a method with the wrong signature (missing a parameter, wrong parameter name) — allauth calls these methods internally with specific arguments; a mismatched signature crashes at call time, not at class-definition time, making the bug harder to spot immediately.
# ❌ Forgetting from __future__ import annotations (or the TYPE_CHECKING guard) when referencing a type that's only conditionally imported — causes a NameError the moment the file loads, not just when the annotation is "used."
# ❌ Unconditionally overwriting fields in populate_user instead of checking if not user.first_name first — risks discarding correctly-populated data from allauth's own default logic.
# ❌ Defining these adapter classes but forgetting to register them in settings.py — exactly the same "hook not wired up" mistake as the empty signup forms; the classes existing changes nothing on their own.
# ❌ Using settings.SOME_SETTING directly instead of getattr(settings, "SOME_SETTING", default) when the setting isn't guaranteed to always be defined — risks a hard crash instead of a graceful fallback.
# 12. Think like the original developer
# "allauth handles the entire signup flow — I can't rewrite its views, but I can plug into the specific extension points it deliberately provides."
# "I need signup availability to be configurable via a setting, for both the normal and social signup paths — and I shouldn't assume that setting will always be explicitly defined, so I'll default safely if it's missing."
# "Social login data varies a lot between providers — I can't fully trust allauth's generic mapping to always populate every field I care about, but I also shouldn't throw away what it does get right. I'll build on top of it, only patching specific gaps."
# "For fields I fall back to filling in manually, I should be defensive there too — the raw provider data might not have the field either, so don't crash, just fall back to empty."
# "Since User and other Django-specific types are only needed for type-checking, not at runtime, I should keep those imports conditional — but that means I need to tell Python not to actually evaluate my type hints at load time, which is exactly what from __future__ import annotations is for."

# That reasoning — "extend the framework's designated hooks rather than fighting it, default defensively wherever an external setting or provider payload might be missing something, and only patch what the framework's own defaults get wrong" — is this file.



