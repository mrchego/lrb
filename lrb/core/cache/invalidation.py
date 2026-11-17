"""Invalidate cache entries only AFTER the database change is committed.

Why after: with ATOMIC_REQUESTS the whole request is one transaction. If we
deleted the cache entry first, another request could re-fill it from the
still-uncommitted OLD data before our commit lands, and the stale value would
live until its TTL. Deleting at commit closes that window.

Known limit (fixed later by version-checked writes): a reader that loaded old
data *before* the commit can still write it back *after* our delete. The TTL
bounds how long that can last.

Also here: register_model_invalidation(), which lets an app say "when a Product
is saved or deleted, clear this policy for that company" in one line, with no
changes to its services.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from django.apps import apps
from django.db import connection, transaction
from django.db.models.signals import post_delete, post_save
from django_tenants.utils import schema_context

from lrb.core.cache.client import cache_delete_many
from lrb.core.cache.keys import policy_key
from lrb.core.cache.policies import CachePolicy

logger = logging.getLogger(__name__)


def delete_after_commit(*, keys: Iterable[str], schema_name: str | None = None) -> None:
    """Delete `keys` once the surrounding transaction commits.

    KEY_FUNCTION prefixes every key with a schema name, so the delete must run under the
    schema the entries were WRITTEN under. By default that is the schema active right now.
    Pass `schema_name` when the data belongs to a company but the write is happening from a
    different schema (for example a platform admin editing a company's row on the public site).
    """
    key_list = list(keys)  # evaluate now; a generator could be spent by commit time
    if not key_list:
        return

    # Remember the schema as it is NOW (or the one we were told), not as it is at commit time.
    schema = schema_name or connection.schema_name

    def _delete() -> None:
        if connection.schema_name == schema:
            ok = cache_delete_many(key_list)
        else:
            with schema_context(schema):
                ok = cache_delete_many(key_list)
        if not ok:
            logger.error(
                "Cache invalidation FAILED for %d key(s); stale entries stay until TTL",
                len(key_list),
            )

    # Outside a transaction, on_commit runs immediately.
    transaction.on_commit(_delete, robust=True)


def invalidate_policy(
    *,
    policy: CachePolicy,
    company_id,
    params: Mapping[str, str] | None = None,
    schema_name: str | None = None,
) -> None:
    """Drop one cached value of a policy (after commit). The next read recomputes it."""
    delete_after_commit(
        keys=[policy_key(policy=policy, company_id=company_id, params=params)],
        schema_name=schema_name,
    )


@dataclass(frozen=True)
class _ModelRule:
    model: str  # "app_label.ModelName"
    policies: tuple[CachePolicy, ...]
    company_field: str
    schema_from_company: bool = False


_RULES: list[_ModelRule] = []
_CONNECTED = False  # True once ready() has connected the rules registered so far


def register_model_invalidation(
    *,
    model: str,
    policies: Sequence[CachePolicy],
    company_field: str = "company_id",
    schema_from_company: bool = False,
) -> None:
    """Clear `policies` for the row's company whenever `model` is saved or deleted.

    Only works for changes that fire Django signals. QuerySet.update(),
    bulk_create() and bulk_update() do not, so those rely on the policy TTL.

    schema_from_company: set True for models that live in the SHARED (public) schema but hold
    per-company data (like CompanySettings). Cached entries were written under the COMPANY'S
    schema, yet an admin may edit the row while the public schema is active. With this flag the
    delete targets the company's own schema, whichever schema the save happens in. Leave it
    False for tenant-schema models: the schema active at save time already IS the company's.
    """
    rule = _ModelRule(
        model=model,
        policies=tuple(policies),
        company_field=company_field,
        schema_from_company=schema_from_company,
    )
    if rule in _RULES:
        return
    _RULES.append(rule)
    if _CONNECTED:
        # Registered after startup finished (a policy file imported late): hook it up now,
        # otherwise it would silently never fire.
        _connect_rule(rule)


def _schema_of_company(instance, rule: _ModelRule, company_id) -> str | None:
    """The company's own schema name, or None if it cannot be determined."""
    relation = rule.company_field.removesuffix("_id")
    company = getattr(instance, relation, None)
    schema = getattr(company, "schema_name", None)
    if schema:
        return schema
    from django_tenants.utils import get_tenant_model  # lazy: needs the app registry

    return (
        get_tenant_model().objects.filter(pk=company_id).values_list("schema_name", flat=True).first()
    )


def _make_handler(rule: _ModelRule):
    def _handler(sender, instance, **kwargs) -> None:
        if kwargs.get("raw"):  # fixture loading
            return
        company_id = getattr(instance, rule.company_field, None)
        if not company_id:
            return
        schema = _schema_of_company(instance, rule, company_id) if rule.schema_from_company else None
        for policy in rule.policies:
            invalidate_policy(policy=policy, company_id=str(company_id), schema_name=schema)

    return _handler


def _connect_rule(rule: _ModelRule) -> None:
    model = apps.get_model(rule.model)
    handler = _make_handler(rule)
    uid = f"lrb-cache-{rule.model}-{'+'.join(p.name for p in rule.policies)}"
    # weak=False: the handler is a closure and would be garbage-collected otherwise.
    post_save.connect(handler, sender=model, weak=False, dispatch_uid=f"{uid}-save")
    post_delete.connect(handler, sender=model, weak=False, dispatch_uid=f"{uid}-delete")


def connect_model_invalidation() -> None:
    """Called once from CoreConfig.ready(), after policies are discovered."""
    global _CONNECTED
    for rule in _RULES:
        _connect_rule(rule)
    _CONNECTED = True





# Big picture
# This file makes sure cached values are deleted after a database change is safely saved.

# Imagine a shop changes a product’s price:
# 1. The database starts changing the price, but hasn’t finished saving it yet.
# 2. Another request asks for that product and reads the old price.
# 3. If the cache was cleared too early, that other request could put the old price back into the cache.
# 4. This code schedules the cache deletion to happen after the database transaction commits.
# A transaction is a group of database changes treated as one unit. “Commit” means the database confirms that the changes are saved.

# This file also connects Django’s save and delete notifications—called signals—to cache invalidation. “Invalidate” means remove a cached value so the next read has to calculate or fetch it again.
# Imports and setup
# """Invalidate cache entries only AFTER the database change is committed.
# ...
# """
# This is the file’s docstring: a description of its purpose and an important limitation.

# It explains why deletion happens after commit. It also says there is still a possible timing issue: a reader might load old data before the commit, then write that old data back after the cache is deleted. The time-to-live, or TTL, limits how long that stale value remains.

# The docstring also introduces register_model_invalidation(), which lets other code say which cached policies to clear when a model is saved or deleted.
# from __future__ import annotations
# This tells Python to postpone handling type annotations. Type annotations are notes about the kinds of values functions expect and return.
# import logging
# Imports Python’s logging tools so this file can report problems.
# from dataclasses import dataclass
# Imports dataclass, a helper for making classes that mainly store data.
# from typing import Iterable, Mapping, Sequence
# Imports type-description tools:
# - Iterable: a group of values that can be read one at a time.
# - Mapping: key-and-value data, like a dictionary.
# - Sequence: ordered values, like a list or tuple.
# from django.apps import apps
# Imports Django’s app registry. It can find a model by its name.
# from django.db import connection, transaction
# Imports:
# - connection, which gives information about the current database connection, including its active schema.
# - transaction, which provides transaction tools such as running a function after a commit.
# from django.db.models.signals import post_delete, post_save
# Imports two Django signals:
# - post_save is sent after a model object is saved.
# - post_delete is sent after a model object is deleted.
# A signal is like a notification: “This event just happened.”
# from django_tenants.utils import schema_context
# Imports a tool for temporarily switching to a database schema.

# A schema is a separate database space. This app uses schemas to keep different companies’ data apart.
# from lrb.core.cache.client import cache_delete_many
# from lrb.core.cache.keys import policy_key
# from lrb.core.cache.policies import CachePolicy
# These import three parts from the app:
# - cache_delete_many: a safe helper for deleting cache keys.
# - policy_key: builds the cache key for a policy.
# - CachePolicy: the type used to describe a cache policy.
# The earlier cache-wrapper code is relevant here: cache_delete_many() goes through the cache safety logic.
# logger = logging.getLogger(__name__)
# Creates a logger for this file. __name__ identifies the current module.
# Scheduling a deletion after commit
# def delete_after_commit(*, keys: Iterable[str], schema_name: str | None = None) -> None:
# Defines a function that schedules cache keys to be deleted after the current database transaction commits.
# - * means the arguments must be named, such as keys=[...].
# - keys is a group of text cache keys.
# - schema_name is an optional schema name. None means no schema was supplied.
# - -> None means the function does not return a result.
# """Delete `keys` once the surrounding transaction commits.
# ...
# """
# This docstring explains the schema handling.

# Cache keys are prefixed with a schema name. So if a value was saved under a company’s schema, the deletion must run under that same schema. If no schema is given, the function uses the schema active now.
# key_list = list(keys)  # evaluate now; a generator could be spent by commit time
# Converts keys into a list and stores it.

# Why do that now? keys might be a generator, which is like a one-time stream of values. By the time the transaction commits, that stream might already be empty. Making a list now preserves the keys for later.
# if not key_list:
#     return
# If the list is empty, there is nothing to delete, so the function ends early.
# schema = schema_name or connection.schema_name
# Chooses which schema to use:
# - If schema_name was supplied and is non-empty, use it.
# - Otherwise, use the schema currently active on the database connection.
# The or here means “use the left value if it is available; otherwise use the right value.”
# def _delete() -> None:
# Defines a small function inside delete_after_commit(). This is a nested function. It contains the deletion work that will happen later.
# if connection.schema_name == schema:
#     ok = cache_delete_many(key_list)
# Checks whether the connection is already using the schema where these cache keys belong.

# If it is, delete the keys directly. The result is stored in ok.
# else:
#     with schema_context(schema):
#         ok = cache_delete_many(key_list)
# If the active schema is different, temporarily switch to the correct schema using schema_context(schema), then delete the keys.

# The with block manages that temporary context. When the block ends, the context manager restores the previous schema context.
# if not ok:
# Checks whether the cache deletion helper reported failure.
# logger.error(
#     "Cache invalidation FAILED for %d key(s); stale entries stay until TTL",
#     len(key_list),
# )
# If deletion failed, logs an error. %d is replaced with the number of keys.

# This message warns that the old cache entries may remain until their TTL expires.
# transaction.on_commit(_delete, robust=True)
# Registers _delete to run after the surrounding database transaction commits.

# If there is no transaction open, Django runs the callback immediately.

# robust=True tells Django to handle an exception from this callback without letting it break the rest of the commit callbacks. The cache wrapper itself handles Redis connection errors, while this option helps keep a callback error from disrupting other commit work.
# Invalidating one policy’s cache entry
# def invalidate_policy(
#     *,
#     policy: CachePolicy,
#     company_id,
#     params: Mapping[str, str] | None = None,
#     schema_name: str | None = None,
# ) -> None:
# Defines a helper to invalidate one cached value.
# - policy describes which kind of cached value to clear.
# - company_id identifies the company. Its type is not specified in this signature.
# - params is optional key-and-value information used to identify a particular version of the policy’s cached value.
# - schema_name optionally says which schema owns that cached entry.
# - -> None means this helper doesn’t return a value.
# """Drop one cached value of a policy (after commit). The next read recomputes it."""
# This says the next read must fetch or calculate the value again after the cache entry is dropped.
# delete_after_commit(
#     keys=[policy_key(policy=policy, company_id=company_id, params=params)],
#     schema_name=schema_name,
# )
# This builds one cache key and schedules it for deletion.

# Step by step:
# 1. policy_key(...) creates the key using the policy, company ID, and optional parameters.
# 2. [ ... ] puts that single key into a list.
# 3. delete_after_commit(...) schedules the deletion for after the database commit.
# Describing rules for models
# @dataclass(frozen=True)
# class _ModelRule:
# Defines a small class for storing one invalidation rule.
# - @dataclass asks Python to create basic data-handling features for the class.
# - frozen=True makes each rule unchangeable after it is created.
# - The leading underscore suggests this class is for internal use.
# model: str  # "app_label.ModelName"
# Stores the model’s name as text, such as "shop.Product".
# policies: tuple[CachePolicy, ...]
# Stores the policies to invalidate. tuple[CachePolicy, ...] means “a tuple containing zero or more CachePolicy values.”
# company_field: str
# Stores the name of the model field that identifies its company.
# schema_from_company: bool = False
# Stores whether the company’s own schema should be found and used. It defaults to False.
# _RULES: list[_ModelRule] = []
# _CONNECTED = False
# Creates two shared values:
# - _RULES starts as an empty list. Rules will be added here.
# - _CONNECTED tracks whether the rules have been connected to Django’s signals.
# The comment says _CONNECTED becomes true once ready() has connected the rules registered so far. ready() is a Django app-startup method; the connection happens later in connect_model_invalidation().
# Registering a model rule
# def register_model_invalidation(
#     *,
#     model: str,
#     policies: Sequence[CachePolicy],
#     company_field: str = "company_id",
#     schema_from_company: bool = False,
# ) -> None:
# Defines a function that registers a rule.

# For example, another file could say:
# When a Product is saved or deleted, clear this policy for its company.

# The defaults are:
# - The company field is named "company_id".
# - The company’s schema is not looked up separately.
# """Clear `policies` for the row's company whenever `model` is saved or deleted.
# ...
# """
# The docstring explains what the rule does and its limits.

# A row is one record in a database table. Django signals fire for normal model saves and deletes, but this docstring warns they do not fire for operations such as QuerySet.update(), bulk_create(), and bulk_update(). Those changes rely on the cache TTL instead.

# It also explains schema_from_company: use it for data stored in the public schema when the cached value belongs to a company schema.
# rule = _ModelRule(
#     model=model,
#     policies=tuple(policies),
#     company_field=company_field,
#     schema_from_company=schema_from_company,
# )
# Creates a rule object using the supplied settings.

# tuple(policies) turns the sequence into a tuple. That fits the rule’s fixed, unchangeable data structure.
# if rule in _RULES:
#     return
# Checks if this exact rule is already registered. If so, stop here to avoid adding it twice.
# _RULES.append(rule)
# Adds the new rule to the list.
# if _CONNECTED:
# Checks whether startup has already connected the rules registered so far.
# _connect_rule(rule)
# If signals were already connected during startup, connect this new rule immediately. Otherwise, it would stay in the list without being connected.
# Finding a company’s schema
# def _schema_of_company(instance, rule: _ModelRule, company_id) -> str | None:
# Defines a helper that tries to find the company’s schema name.
# - instance is the model object that was saved or deleted.
# - rule is the invalidation rule for that model.
# - company_id identifies its company.
# - The result is a schema name (str) or None if it can’t be found.
# """The company's own schema name, or None if it cannot be determined."""
# Explains the helper’s result.
# relation = rule.company_field.removesuffix("_id")
# Gets the relation field’s name by removing _id from the configured company field.

# If company_field is "company_id", then relation becomes "company".

# This assumes the model has a related object accessible with that name.
# company = getattr(instance, relation, None)
# Looks for an attribute named by relation on the model object.

# For example, if relation is "company", this is like asking for instance.company. If it does not exist, use None instead of raising an error.
# schema = getattr(company, "schema_name", None)
# Looks for a schema_name attribute on the company object. If that attribute exists and has a value, use it.
# if schema:
#     return schema
# If a schema name was found, return it immediately.
# from django_tenants.utils import get_tenant_model  # lazy: needs the app registry
# If the company object did not provide a schema, import a Django Tenants helper to find the tenant model.

# The import is inside the function, so it happens only when this path is needed. The comment says this helper needs Django’s app registry, which must be ready before it is used.
# return (
#     get_tenant_model().objects.filter(pk=company_id).values_list("schema_name", flat=True).first()
# )
# This looks up the company in the database and returns its schema name:
# 1. get_tenant_model() gets the tenant/company model class.
# 2. .objects is Django’s way to make database queries for that model.
# 3. .filter(pk=company_id) asks for the row whose primary key matches this company ID. A primary key is the value that uniquely identifies a database row.
# 4. .values_list("schema_name", flat=True) asks for just the schema_name field.
# 5. .first() returns the first result, or None if there was no match.
# Making a signal handler
# def _make_handler(rule: _ModelRule):
# Defines a helper that creates a signal-handling function for a rule.

# It doesn’t show a return type here, but it returns the nested _handler function below.
# def _handler(sender, instance, **kwargs) -> None:
# Defines the actual function Django will call when a matching signal fires.
# - sender is the model class that sent the signal.
# - instance is the specific model object that was saved or deleted.
# - **kwargs collects extra named information Django sends with the signal.
# if kwargs.get("raw"):
#     return
# If raw is true, this change came from fixture loading. A fixture is saved data loaded into a Django app, often for setup or testing.

# The handler skips invalidation in that case.
# company_id = getattr(instance, rule.company_field, None)
# Gets the company ID from the model object. For the default "company_id" field, this is like reading instance.company_id.

# If the field is missing, use None.
# if not company_id:
#     return
# If there is no company ID, stop. Without a company, this handler doesn’t know which company’s cached entries to clear.
# schema = _schema_of_company(instance, rule, company_id) if rule.schema_from_company else None
# This is a conditional expression: a compact if/else.
# - If rule.schema_from_company is true, look up the company’s schema.
# - Otherwise, set schema to None. delete_after_commit() will then use the currently active schema.
# for policy in rule.policies:
# Starts a loop. It repeats the indented work once for each policy in the rule.
# invalidate_policy(policy=policy, company_id=str(company_id), schema_name=schema)
# Schedules that policy’s cache key for deletion.

# str(company_id) converts the company ID to text. The policy key builder can then receive it in the format expected here.
# return _handler
# Returns the newly created handler function. The signal connection code will use it.
# Connecting a rule to Django signals
# def _connect_rule(rule: _ModelRule) -> None:
# Defines an internal helper that connects one rule to Django’s save and delete signals.
# model = apps.get_model(rule.model)
# Asks Django’s app registry for the model class named in the rule, such as "shop.Product".
# handler = _make_handler(rule)
# Creates the handler function for this rule.
# uid = f"lrb-cache-{rule.model}-{'+'.join(p.name for p in rule.policies)}"
# Builds a unique-looking text ID for the signal connections.

# Breaking it down:
# - f"..." is a formatted string.
# - rule.model inserts the model name.
# - '+'.join(...) combines policy names with + between them.
# - p.name for p in rule.policies means “take the name of each policy.”
# The resulting ID helps Django recognize this particular connection.
# post_save.connect(handler, sender=model, weak=False, dispatch_uid=f"{uid}-save")
# Connects the handler to the model’s save signal.
# - handler is the function to run.
# - sender=model means only saves of this model should trigger it.
# - dispatch_uid gives the connection a unique ID, helping avoid duplicate connections.
# - weak=False tells Django to keep a strong reference to this handler. The comment explains why.
# post_delete.connect(handler, sender=model, weak=False, dispatch_uid=f"{uid}-delete")
# Does the same for deletions.

# Now saving or deleting an object of this model can run the handler.
# Connecting all registered rules
# def connect_model_invalidation() -> None:
# Defines the function that connects every rule registered so far.
# """Called once from CoreConfig.ready(), after policies are discovered."""
# The docstring says this is called during Django app startup, after policy definitions have been discovered.
# global _CONNECTED
# Says that this function will update the shared _CONNECTED value, rather than creating a new local variable with the same name.
# for rule in _RULES:
#     _connect_rule(rule)
# Loops through every registered rule and connects it to the model’s save and delete signals.
# _CONNECTED = True
# Records that startup connection has finished.

# From now on, if a new rule is registered later, register_model_invalidation() sees this flag and connects that rule immediately.
# How everything connects
# The normal flow is:
# Application registers a model rule
#         ↓
# Startup connects the rule to save and delete signals
#         ↓
# A matching model is saved or deleted
#         ↓
# Django calls the handler
#         ↓
# The handler finds the company and relevant policies
#         ↓
# Each policy's cache key is built
#         ↓
# Deletion is scheduled after the database commit
#         ↓
# The cache entry is deleted under the schema where it was written
# For example, if a Product is saved:
# 1. Django sends post_save.
# 2. This file’s handler runs for that product.
# 3. It gets the product’s company ID.
# 4. It builds the cache key for each registered policy.
# 5. It schedules deletion using transaction.on_commit().
# 6. Once the database transaction commits, the cache entry is deleted.
# If the save is rolled back instead of committed, the scheduled callback does not run, so the cache is not cleared based on a database change that never became final.
# Summary table
# Name	Simple meaning
# delete_after_commit()	Delete cache keys once the database confirms its changes
# invalidate_policy()	Build and schedule deletion of one policy’s cache entry
# _ModelRule	Stores which model changes should clear which policies
# register_model_invalidation()	Adds a rule to the list
# _schema_of_company()	Finds the schema belonging to a company
# _make_handler()	Creates the function that responds to model signals
# _connect_rule()	Connects one rule to save and delete notifications
# connect_model_invalidation()	Connects all registered rules during startup
# transaction.on_commit()	Runs a function after a successful database commit
# Signal	A notification that a save or delete event happened


# The key idea to remember is: a database change triggers a cache deletion, but the deletion waits until the database change is committed. That timing helps avoid clearing the cache too early while the old database data is still visible.
