"""The only place cache keys are built.

Every key starts with a namespace and a company id, so two companies can never
share a key. Django's KEY_FUNCTION (django_tenants.cache.make_key) adds the
schema name on top of this, but it reads the *current* database connection,
which is wrong in places like Celery tasks. Putting the company id into the
key itself means correctness does not depend on connection state.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Iterable, Mapping

from lrb.core.tenancy import get_current_tenant, require_company_id

if TYPE_CHECKING:
    from lrb.core.cache.policies import CachePolicy

# Letters, digits, underscore, dot, hyphen. No ":" (our separator), no spaces.
# A part containing ":" could make ("a:b",) collide with ("a", "b").
_SAFE_PART = re.compile(r"^[A-Za-z0-9_.\-]{1,128}$")


def current_tenant_scope() -> str:
    """Company id of the schema active right now. Fails closed on the public schema."""
    return str(get_current_tenant().pk)


def build_key(*, namespace: str, company_id, parts: Iterable[object]) -> str:
    company = require_company_id(company_id)
    pieces = [namespace, company, *(str(p) for p in parts)]
    for piece in pieces:
        if not _SAFE_PART.match(piece):
            raise ValueError(f"Unsafe cache key part: {piece!r}")
    return ":".join(pieces)


def policy_key(*, policy: "CachePolicy", company_id, params: Mapping[str, str] | None = None) -> str:
    """Key for one cached value of a policy. Params are sorted so order never matters."""
    parts = [f"{name}-{value}" for name, value in sorted((params or {}).items())]
    return build_key(namespace=policy.name, company_id=company_id, parts=parts)


def lock_key(key: str) -> str:
    return f"{key}:lock"


def refresh_lock_key(key: str) -> str:
    return f"{key}:refresh"


# Big picture
# This file is the one place in the app that builds cache keys.

# A cache key is like a label on a storage box. The app uses the label to find the saved value again. If two companies accidentally use the same label, one company could get another company’s cached data.

# This file helps prevent that by putting the company ID in every key. It also checks that each piece is safe to use in a key.

# For example, a key might look like:
# sales_summary:42:month-2026-11
# That means:
# - sales_summary is the kind of cached value.
# - 42 is the company ID.
# - month-2026-11 is an optional detail about this value.
# The opening comment mentions a second layer: Django’s configured KEY_FUNCTION adds the active database schema to a key. The code here also includes the company ID directly, so the key still identifies the company even when code runs in a place where the database connection’s current schema might not match the company.
# Imports and setup
# File description
# """The only place cache keys are built.
# ...
# """
# This is the file’s docstring, a description of the file.

# It explains the safety problem the code is solving: Django’s schema-based key prefix comes from the current database connection. In a background job, such as a Celery task, that connection may not be set to the company’s schema. Putting the company ID directly into the key makes the company part explicit.
# from __future__ import annotations
# Tells Python to postpone handling type annotations. A type annotation is a note about what kind of value a function expects or returns.
# import re
# Imports Python’s regular expression tool. A regular expression is a pattern used to check whether text follows certain rules.
# from typing import TYPE_CHECKING, Iterable, Mapping
# Imports tools used for type annotations:
# - TYPE_CHECKING lets code import a type only for type-checking tools, without importing it during normal program execution.
# - Iterable means a group of values that can be read one at a time.
# - Mapping means key-and-value data, such as a dictionary.
# from lrb.core.tenancy import get_current_tenant, require_company_id
# Imports two app-specific helpers:
# - get_current_tenant() gets the company, or tenant, associated with the active schema.
# - require_company_id() checks that a company ID is acceptable.
# Their exact checks are not shown in this file, so we shouldn’t guess how they behave internally.
# if TYPE_CHECKING:
#     from lrb.core.cache.policies import CachePolicy
# This imports CachePolicy only when a type checker is examining the code.

# A type checker is a tool that looks for mistakes involving the kinds of values passed around. This import helps describe the policy argument below, without requiring the real import during normal execution.
# Checking safe key parts
# # Letters, digits, underscore, dot, hyphen. No ":" (our separator), no spaces.
# # A part containing ":" could make ("a:b",) collide with ("a", "b").
# _SAFE_PART = re.compile(r"^[A-Za-z0-9_.\-]{1,128}$")
# The comments explain what characters are allowed in one part of a key:
# - Letters
# - Numbers
# - Underscores
# - Dots
# - Hyphens
# A colon is not allowed because this code uses colons to separate key parts.

# re.compile(...) prepares the regular expression pattern so the code can use it to check text.

# The pattern means:
# - ^ — start of the text.
# - [A-Za-z0-9_.\-] — one allowed character.
# - {1,128} — between 1 and 128 allowed characters.
# - $ — end of the text.
# So a part such as "month-2026" is allowed, but "month:2026" contains a colon and is rejected.

# Why ban colons? Without the rule, these two sets of parts could become hard to tell apart after joining:
# ("a:b",)    → a:b
# ("a", "b")  → a:b
# The colon separator would no longer show where one part ends and the next begins.
# Getting the current company ID
# def current_tenant_scope() -> str:
# Defines a function named current_tenant_scope.
# - -> str says it returns text.
# """Company id of the schema active right now. Fails closed on the public schema."""
# The docstring says this gets the company ID for the currently active schema. “Fails closed on the public schema” means that if the current schema does not represent a company, the helper is expected to stop with an error rather than quietly use a possibly wrong company ID. The exact behavior depends on get_current_tenant().
# return str(get_current_tenant().pk)
# Step by step:
# 1. get_current_tenant() gets the current company.
# 2. .pk reads its primary key. A primary key is the database value that uniquely identifies a row.
# 3. str(...) converts that value to text.
# 4. return sends the text back to the caller.
# For example, if the company’s primary key is the number 42, this function returns "42".
# Building a key from parts
# def build_key(*, namespace: str, company_id, parts: Iterable[object]) -> str:
# Defines the general-purpose key-building function.
# - * means callers must provide the arguments by name.
# - namespace: str is a text label for the type of cached value.
# - company_id identifies the company; its type isn’t specified here.
# - parts: Iterable[object] is a group of extra values.
# - -> str says the function returns the complete key as text.
# For example, a call might look like:
# build_key(namespace="sales", company_id=42, parts=["month-2026-11"])
# company = require_company_id(company_id)
# Checks the supplied company ID using the imported helper and saves its result in company.

# This file shows that the helper is called, but not what validation it performs. Its name suggests it requires a valid company ID.
# pieces = [namespace, company, *(str(p) for p in parts)]
# Builds a list of key pieces.
# - Start with the namespace.
# - Add the company ID.
# - Convert each extra part to text and add it too.
# - * in the list spreads those converted values into the list.
# For the example above, the list would be similar to:
# ["sales", "42", "month-2026-11"]
# for piece in pieces:
# Starts a loop. The code inside repeats once for each piece.
# if not _SAFE_PART.match(piece):
# Checks each piece against the safe-character pattern.
# - _SAFE_PART.match(piece) checks whether the piece follows the allowed format.
# - not means the if is true when it does not follow the format.
# raise ValueError(f"Unsafe cache key part: {piece!r}")
# If a piece is unsafe, this stops the function by raising a ValueError.
# - ValueError means the program received a value it cannot accept here.
# - The f"..." creates a formatted message.
# - {piece!r} includes a useful representation of the rejected value, often with quotes.
# For instance, a colon-containing piece might raise an error like:
# Unsafe cache key part: 'a:b'
# Raising an error is useful here: it prevents a badly formed key from being created silently.
# return ":".join(pieces)
# Joins the list into one text string, putting a colon between each piece.

# For example:
# ["sales", "42", "month-2026-11"]
# becomes:
# sales:42:month-2026-11
# The safety check is what makes joining with colons unambiguous: none of the pieces can contain a colon of its own.
# Building a key for a policy
# def policy_key(
#     *,
#     policy: "CachePolicy",
#     company_id,
#     params: Mapping[str, str] | None = None,
# ) -> str:
# Defines a helper for making a key from a cache policy.
# - policy describes the kind of cached value. Its type is written as "CachePolicy" because it is imported only for type checking.
# - company_id identifies the company.
# - params is optional key-and-value information. It can be a mapping such as {"month": "2026-11"}.
# - | None means the value may either be the described type or None.
# - = None makes it optional; if not provided, it defaults to None.
# - -> str means a text key is returned.
# """Key for one cached value of a policy. Params are sorted so order never matters."""
# The docstring explains that parameters are sorted. That way, the same information in a different insertion order still creates the same key.

# For example, these should result in the same parameter order:
# {"month": "11", "year": "2026"}
# {"year": "2026", "month": "11"}
# parts = [f"{name}-{value}" for name, value in sorted((params or {}).items())]
# This builds the extra parts of the key from params.

# Step by step:
# 1. params or {} uses params if it was supplied; otherwise it uses an empty dictionary.
# 2. .items() gets each name and value pair.
# 3. sorted(...) puts the pairs into a consistent order.
# 4. for name, value in ... takes each pair apart into two names. This is called unpacking.
# 5. f"{name}-{value}" combines each pair into text.
# For example:
# {"month": "11", "year": "2026"}
# becomes parts equivalent to:
# ["month-11", "year-2026"]
# return build_key(namespace=policy.name, company_id=company_id, parts=parts)
# Passes the policy’s name, company ID, and extra parts to the general key builder.

# This means policy_key() relies on build_key() to validate the pieces and join them safely.
# Making lock-related keys
# def lock_key(key: str) -> str:
# Defines a function that takes a key and returns another text key.
# return f"{key}:lock"
# Adds ":lock" to the end.

# For example:
# sales:42:month-2026-11
# becomes:
# sales:42:month-2026-11:lock
# That gives the lock its own key related to the cached value.
# def refresh_lock_key(key: str) -> str:
# Defines another function for making a refresh-lock key.
# return f"{key}:refresh"
# Adds ":refresh" to the end. For the same example, the result would be:
# sales:42:month-2026-11:refresh
# These suffixes are added after build_key() checks the key parts, so they are not checked by _SAFE_PART here. They are fixed suffixes chosen by the code.
# How the pieces fit together
# A typical flow looks like this:
# A caller has a policy, company ID, and optional parameters
#         ↓
# policy_key() turns those into text parts
#         ↓
# build_key() adds the namespace and company ID
#         ↓
# build_key() checks that every part is safe
#         ↓
# The parts are joined with colons
#         ↓
# The caller uses the key to read or write the cache
# For example, suppose the policy name is "sales", the company ID is 42, and the parameters are {"month": "2026-11"}. The key could be:
# sales:42:month-2026-11
# The company ID is included directly in the key, so it does not depend only on which database schema happens to be active when the code runs.
# Summary
# Part	Simple meaning
# current_tenant_scope()	Gets the current company’s ID as text
# build_key()	Checks and joins the pieces of a cache key
# policy_key()	Builds a key for one policy and its parameters
# lock_key()	Adds :lock to a key
# refresh_lock_key()	Adds :refresh to a key
# _SAFE_PART	Defines the allowed characters for each key part
# require_company_id()	Checks the company ID before it is used


# The main idea: cache keys should clearly identify both the kind of value and the company it belongs to. This file builds those keys in one consistent, checked way.