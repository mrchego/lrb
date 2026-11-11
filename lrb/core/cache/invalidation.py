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


def delete_after_commit(*, keys: Iterable[str]) -> None:
    key_list = list(keys)  # evaluate now; a generator could be spent by commit time
    if not key_list:
        return

    # KEY_FUNCTION prefixes keys with the schema active when delete runs.
    # Remember the schema as it is NOW so the delete hits the same keys.
    schema = connection.schema_name

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
    *, policy: CachePolicy, company_id, params: Mapping[str, str] | None = None
) -> None:
    """Drop one cached value of a policy (after commit). The next read recomputes it."""
    delete_after_commit(keys=[policy_key(policy=policy, company_id=company_id, params=params)])


@dataclass(frozen=True)
class _ModelRule:
    model: str  # "app_label.ModelName"
    policies: tuple[CachePolicy, ...]
    company_field: str


_RULES: list[_ModelRule] = []
_CONNECTED = False  # True once ready() has connected the rules registered so far


def register_model_invalidation(
    *, model: str, policies: Sequence[CachePolicy], company_field: str = "company_id"
) -> None:
    """Clear `policies` for the row's company whenever `model` is saved or deleted.

    Only works for changes that fire Django signals. QuerySet.update(),
    bulk_create() and bulk_update() do not, so those rely on the policy TTL.
    """
    rule = _ModelRule(model=model, policies=tuple(policies), company_field=company_field)
    if rule in _RULES:
        return
    _RULES.append(rule)
    if _CONNECTED:
        # Registered after startup finished (a policy file imported late): hook it up now,
        # otherwise it would silently never fire.
        _connect_rule(rule)


def _make_handler(rule: _ModelRule):
    def _handler(sender, instance, **kwargs) -> None:
        if kwargs.get("raw"):  # fixture loading
            return
        company_id = getattr(instance, rule.company_field, None)
        if not company_id:
            return
        for policy in rule.policies:
            invalidate_policy(policy=policy, company_id=str(company_id))

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