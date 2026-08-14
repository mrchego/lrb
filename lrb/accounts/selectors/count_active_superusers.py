from typing import Optional, Iterable
from lrb.accounts.models import User

def count_active_superusers(*, company_id: str, exclude_ids:Optional[Iterable[str]] = None) -> int:
    qs = User.objects.filter(company_id=company_id, is_superuser=True, is_active=True)
    if exclude_ids:
        qs = qs.exclude(pk__in=exclude_ids)
    return qs.count()


# 1. Purpose — Why this exists

# What problem is this solving?
# Somewhere in your RBAC project there's almost certainly a rule like: "a company must always have at least one active superuser." Before you let someone deactivate, delete, or demote a superuser, you need to know: if I remove this person, will the company have zero superusers left? This function answers that question — it counts how many active superusers a company currently has.

# Why not just write the logic directly where it's needed?
# Because "how many active superusers does this company have" is a question you'll need to ask from multiple places — a service that deactivates a user, a service that removes the superuser role, a service that deletes a staff account. If you wrote the query inline every time, you'd have the same filter logic copy-pasted in five files. The moment the definition of "active superuser" changes (say, you later add a is_suspended flag), you'd have to hunt down and fix every copy. Centralizing it in one function means you fix it once.

# When is this used in a real project?
# Right before a "dangerous" action — deactivating a user, revoking the superuser role, deleting an account — a service calls this function first to check it's safe to proceed.

# What breaks without it?
# Without a guard like this, someone could deactivate the last superuser at a company, and now nobody at that company has the power to manage staff, roles, or permissions. The company is locked out of its own admin functions — a real, painful bug class in any RBAC system.

# 2. Imports — explained like you've never programmed
# python
# from typing import Optional, Iterable
# from lrb.accounts.models import User

# What is import?
# Python code is split across many files (called modules). import is the instruction "go get code that was written in a different file, and let me use it here." Without imports, every single file would have to redefine everything from scratch — every project would be one giant unreadable file.

# What is from?
# from X import Y means "go into the module X, and pull out only the specific thing called Y." It's more precise than importing the whole module. Compare:

# python
# import typing
# # now you must write: typing.Optional

# from typing import Optional
# # now you can just write: Optional

# from ... import ... saves you from prefixing everything.

# What is typing?
# typing is a module that ships built into Python itself — you didn't install anything to get it. It doesn't contain code that runs; it contains tools for describing what kind of data a variable is supposed to hold. This is purely for humans (and editors/type-checkers) reading the code — Python itself mostly ignores these hints at runtime.

# Optional — means "this could be the stated type, or it could be None."
# Iterable — means "anything you can loop over" (a list, a tuple, a set, a generator — doesn't matter which).

# Why import only Optional and Iterable instead of all of typing?
# typing contains dozens of tools (Optional, List, Dict, Union, Callable, and more). This file only needs two of them. Importing just what you use keeps the top of the file honest — anyone skimming the imports can tell exactly which typing tools matter here, instead of wondering which of twenty are actually used.

# What is lrb.accounts.models?
# The dots here aren't punctuation flourishes — they represent a path through your project's folder structure, the same way / does in a file path. lrb.accounts.models means: inside the lrb package, inside its accounts app, there's a file called models.py. This is not built into Python — it's code that you (or someone on your team) wrote, as part of your own Django project.

# Is User something Django gave you, or something you wrote?
# In your project specifically, this is your project's own User model (living in the accounts app you built), not Django's default built-in user — Django lets you swap in a custom user model, which is exactly what a project with this kind of app structure does.

# Could you write your own importable module like this?
# Yes — any .py file you create becomes something other files can import from, as long as it's inside your project structure. That's literally what lrb.accounts.models is: someone wrote models.py inside accounts/, and now every other file in the project can pull User out of it.

# 3. Signature — every symbol explained
# python
# def count_active_superusers(*, company_id: str, exclude_ids: Optional[Iterable[str]] = None) -> int:

# def
# Means "I'm defining a reusable block of instructions." Instead of writing this query logic every time you need it, you write it once, give it a name, and call that name whenever you need the behavior.

# count_active_superusers
# The function's name — like naming a recipe. Good names describe what comes back: this one very literally tells you "you will get a count of active superusers."

# Parentheses ()
# This is the function's "delivery box" — where information gets handed in. A function with no parameters can't be customized; it does the exact same thing every time. Parameters let the caller control what happens.

# The * — by itself, alone in the parentheses
# This is the part your project treats as non-negotiable, and it's the one symbol here that's easy to misread. A lone * with nothing before or after it is not collecting anything (that's different from *args, which you already know). It's a rule Python enforces: "everything listed after this * must be passed using its keyword name — you are not allowed to pass it positionally."

# Concretely, this function forbids:

# python
# count_active_superusers("acme-inc")  # ❌ TypeError — positional arg not allowed

# and requires:

# python
# count_active_superusers(company_id="acme-inc")  # ✅

# This is exactly your project's "keyword-only arguments on all service functions" convention, made visible in real syntax for the first time in something we've walked through together.

# company_id: str
# company_id is a parameter — a placeholder, like a blank on a form: Dear _______. You don't know its value yet; the caller fills it in. The : str after it is a type hint — "I expect whoever calls this to hand me a string." Python won't stop you if you pass something else; this is a promise for readers (and tools like your IDE) rather than an enforced rule.

# exclude_ids: Optional[Iterable[str]] = None
# Same idea — a placeholder — but with two more pieces:

# The type hint Optional[Iterable[str]] reads as "something you can loop over, where each item is a string — or, this could be None entirely."
# = None is a default value. It means: "if the caller doesn't mention exclude_ids at all, assume None instead of raising an error demanding it."

# Why does this matter? Compare calling it two ways:

# python
# count_active_superusers(company_id="acme-inc")
# count_active_superusers(company_id="acme-inc", exclude_ids=["user-42"])

# Both work. The default value is what makes the second argument optional while company_id (no default) is mandatory.

# -> int
# This arrow-and-type after the closing parenthesis is a return type hint — a promise that this function hands back an integer. Does it change what happens when the code runs? No — Python does not enforce this at runtime; you could technically return a string and Python wouldn't stop you. So why do people write it? Two reasons: (1) it documents the contract for the next person reading the code, so they don't have to trace through the function body to know what they'll get back, and (2) tools like your editor's type checker will flag it if the body doesn't actually return an int, catching bugs before you even run the code.

# 4. Classes

# There's no class here — and that's worth pausing on rather than skipping. Why is this a plain function instead of a class?

# A class makes sense when you need to bundle data with behavior that acts on that data over time — something that has state, gets created, then has multiple methods called on it later (think of your VerificationCode model — it is data with its own lifecycle). This function does none of that. It takes some inputs, runs one query, and gives back a number. There's nothing to remember between calls, nothing to instantiate. A function is the honest, minimal tool for "input goes in, answer comes out, nothing is remembered."

# 5. Body — line by line
# Line 1
# python
# qs = User.objects.filter(company_id=company_id, is_superuser=True, is_active=True)

# Right side first:

# Read it as a journey, one dot at a time:

# User — start at your User model
# .objects — every Django model gets a .objects manager attached automatically; it's your entry point for querying the database table behind this model
# .filter(...) — the verb. "Find rows matching these conditions." Django doesn't run the query yet at this point — it builds up a description of what you want.

# Inside the parentheses, three conditions, all combined with an implicit AND:

# company_id=company_id — only rows belonging to this company
# is_superuser=True — only rows flagged as superuser
# is_active=True — only rows that haven't been deactivated

# Left side:
# qs is a variable name — short for "queryset," Django's own term for "a query that's been built but might not have hit the database yet." We're storing it because we might need to narrow it further on the next line before we actually use it.

# Whole line, plain English:
# "Ask the database for every active, superuser User belonging to this company, and hold onto that (not-yet-executed) query."

# Line 2–3
# python
# if exclude_ids:
#     qs = qs.exclude(pk__in=exclude_ids)

# The condition: if exclude_ids: — this isn't checking exclude_ids == True. In Python, an empty list, empty tuple, or None are all treated as "falsy," so this line really means "if the caller actually gave me something to exclude."

# Right side of the assignment inside the block:

# qs — start from the query we already built
# .exclude(...) — the opposite verb of .filter(): "remove rows matching this condition" instead of "keep rows matching this condition"
# pk__in=exclude_ids — pk means "primary key" (the row's unique ID, regardless of what it's actually named in the database — pk always works). The double-underscore __in is Django's syntax for "is this value inside this collection?" So this reads: "primary key is in the list of IDs to exclude."

# Left side: we reassign qs to this narrowed version — same variable, updated value.

# Whole thing, plain English:
# "If the caller told us to exclude specific users (say, the one currently being deactivated, so we don't count them as still 'existing'), remove those rows from our query."

# Line 4
# python
# return qs.count()

# Right side: qs.count() — tell the queryset to actually go run the query now, but instead of fetching every row's full data, just ask the database for the number of matching rows. This is deliberately more efficient than len(list(qs)), which would pull every row into memory just to count them.

# The verb return: hand this value back to whoever called the function, and stop executing.

# Whole line: "Run the (possibly narrowed) query and give back how many rows matched, as a plain number."

# 6. Beginner questions, answered proactively

# Why * instead of just listing the parameters normally?
# Without it, count_active_superusers("acme-inc", ["user-1"]) would be legal, and six months later nobody reading a call site would know which positional argument is which without checking the function definition. The * trades a tiny bit of typing for permanent clarity at every call site.

# Why Optional[...] = None instead of just = None with no type hint?
# You could write exclude_ids=None with no hint and it would run identically. The hint exists purely to tell a human (or a type checker) "this parameter, when provided, should be an iterable of strings" — without it, a reader has to guess from the parameter name alone.

# Why .filter() then .exclude() instead of one big filter with a "not in" condition baked in?
# Both would work. This version is arguably more readable as a sequence of steps: "get the base set, then conditionally narrow it" mirrors how a human would describe the logic out loud. It also means the .exclude() step is skippable entirely — Django never even builds that clause into the SQL if exclude_ids is empty.

# Why .count() and not len(qs)?
# .count() translates to SELECT COUNT(*) ... in the database — the count happens inside the database engine. len(qs) would force Django to fetch every row into Python first, then count them in memory. For a function whose entire job is "give me a number," fetching full rows would be wasteful.

# Why does the queryset get reassigned to the same variable name (qs = qs.exclude(...)) instead of a new variable?
# Because querysets are immutable — .exclude() doesn't modify qs in place, it returns a new queryset. If you didn't reassign it, the exclusion would be silently thrown away. This is a very common beginner trap in Django (see mistake #2 below).

# 7. Design discussion

# Why keyword-only arguments here specifically?
# This function has two parameters that are both string-ish (company_id: str and exclude_ids containing strings). If positional calling were allowed, count_active_superusers("acme-inc", "user-42") — passing a single string where a list was expected — would be an easy, silent mistake to make and hard to catch. Forcing keywords removes that entire failure mode.

# Why return an int instead of, say, the actual queryset or list of matching users?
# The function's name promises a count, not a list of users. If callers actually needed the users themselves, that would be a different, more expensive function — returning full model instances when you only need a number would be doing unnecessary work every single time this guard runs (and this is the kind of function that might run on every deactivation attempt).

# Trade-off worth naming: this function does not take a for_update() lock or run inside its own transaction. That's a deliberate design choice, not an oversight — it means it's meant to be called from inside a @transaction.atomic service (per your project's convention), where the caller is responsible for making sure the count-check and the subsequent action happen atomically, rather than baking transaction control into every small helper.

# 8. DIY Recipe — build one like this yourself

# How to build your own "count matching rows" service function:

# Name it after the question it answers, not after the mechanism. count_active_superusers, not get_users_filtered.
# Decide what filters define "matching." Write each one as a field=value pair.
# Decide what, if anything, callers should be able to exclude or narrow, and make that an optional keyword parameter with a sensible default (usually None).
# Chain .filter() for required conditions, and conditionally chain .exclude() only when the optional narrowing parameter was actually provided.
# End with .count() if you only need a number — never pull full rows into memory just to count them.
# Force keyword-only args with a lone * the moment you have more than one parameter of the same type (two strings, two lists, etc.) — that's exactly when positional mix-ups become likely.
# 9. General pattern recognition

# This file follows a pattern you'll see constantly in Django service layers — call it the "guard-check query" pattern:

# python
# def count_<thing>(*, <scope>, exclude_ids: Optional[Iterable[str]] = None) -> int:
#     qs = Model.objects.filter(<scope conditions>)
#     if exclude_ids:
#         qs = qs.exclude(pk__in=exclude_ids)
#     return qs.count()

# Anywhere you need to answer "how many X exist under these conditions, ignoring this one I'm about to change," you can reuse this exact shape — swap the model, swap the filter conditions.

# 10. Real project usage

# This almost certainly gets called from inside a write service — something like deactivate_user() or revoke_superuser_role() in rbac.staff or rbac.authorization. The pattern would look like:

# python
# @transaction.atomic
# def deactivate_user(*, actor, target_user_id, ...):
#     require_permission(actor=actor, codename="staff.manage_users")
#     remaining = count_active_superusers(company_id=target.company_id, exclude_ids=[target_user_id])
#     if remaining == 0:
#         raise ValidationError("Cannot deactivate the last active superuser.")
#     ...

# Here, exclude_ids=[target_user_id] is the whole reason that parameter exists — you're asking "if I go through with this, will anyone be left?" before actually performing the deactivation.

# 11. Common beginner mistakes

# ❌ Forgetting to reassign qs after .exclude() — writing qs.exclude(...) on its own line without qs =  means the narrowing is silently discarded, since querysets don't mutate in place.

# ❌ Using len(qs) instead of qs.count() — works, but forces the database to hand over full rows just to throw them away.

# ❌ Passing a single string to exclude_ids instead of a list — e.g. exclude_ids="user-42" instead of exclude_ids=["user-42"]. Because strings are themselves iterable (of characters!), Django would silently try to exclude primary keys matching each character of "user-42" rather than raising an obvious error.

# ❌ Skipping the * when adding a second parameter of the same type "just this once" — that's exactly how positional mix-ups sneak into a codebase.

# 12. Think like the original developer

# If you had no reference and had to invent this yourself, the reasoning would go:

# What problem am I solving? "I need to know, before doing something risky, whether a company would end up with zero active superusers."
# What inputs will I need? At minimum, which company. Probably also: "who am I about to remove," so I can pretend they're already gone while counting.
# What could go wrong? Someone passes the wrong type for the excluded IDs; someone calls it with confusing positional args; the count query becomes expensive if it fetches full rows instead of just counting.
# How should I report the answer? A plain number is the simplest possible contract — the caller decides what "too low" means (probably == 0), this function's only job is counting.
# What should happen if everything works? Just return the number — no side effects, no exceptions, no surprises. That's what makes it safely reusable across many different write services.