"""Per-operation limits for GraphQL.

Every request is POST /graphql/, so an HTTP middleware cannot tell login from a bulk
delete. This Strawberry extension runs once per ROOT field (query/mutation), looks the
field up in policies.OPERATIONS, and spends the right cost from the right policy.

Rejection is raised as a GraphQLError with extensions.code == "RATE_LIMITED". The
middleware then turns it into HTTP 429 + Retry-After.

Safety rule for mutations: once one root field of a request is rejected, every later
root field in that request is rejected too (without spending tokens). A client that
gets 429 can therefore retry the whole request without duplicating work.
"""
from __future__ import annotations

import inspect

from graphql import GraphQLError
from strawberry.extensions import SchemaExtension

from lrb.core.exceptions import ErrorCode
from lrb.core.ratelimit import identity
from lrb.core.ratelimit.engine import limiter, mode
from lrb.core.ratelimit.policies import POLICIES, rule_for
from lrb.core.ratelimit.responses import message
from lrb.core.ratelimit.result import RateLimitResult


def _request(info):
    ctx = info.context
    return ctx.get("request") if isinstance(ctx, dict) else getattr(ctx, "request", None)


def _argument(kwargs: dict, path):
    value = kwargs
    for part in path:
        value = value.get(part) if isinstance(value, dict) else getattr(value, part, None)
        if value is None:
            return None
    return value


def _error(result: RateLimitResult) -> GraphQLError:
    return GraphQLError(message(result),
                        extensions={"code": ErrorCode.RATE_LIMITED, "retryAfter": result.retry_after})


class RateLimitExtension(SchemaExtension):
    def resolve(self, _next, root, info, *args, **kwargs):
        raw = getattr(info, "_raw_info", info)
        if raw.path.prev is not None or raw.field_name.startswith("__") or mode() == "off":
            return _next(root, info, *args, **kwargs)
        request = _request(info)
        if request is None:
            return _next(root, info, *args, **kwargs)

        denied = getattr(request, "_rl_denied", None)
        if denied is not None:
            raise _error(denied)

        rule = rule_for(raw.field_name, raw.operation.operation.value)
        company = identity.company_scope(request)
        actor = identity.actor_id(request)
        subject = identity.normalise_subject(_argument(kwargs, rule.subject)) if rule.subject else None

        result = limiter.check(rule.policy, company=company, ip=identity.client_ip(request),
                               actor=actor, subject=subject, cost=rule.cost)
        request._rl_last = result
        if not result.allowed:
            request._rl_denied = result
            raise _error(result)

        policy = POLICIES[rule.policy]
        if policy.concurrency is None:
            request._rl_passed = True
            return _next(root, info, *args, **kwargs)

        slot = limiter.acquire_slot(rule.policy, company=company, actor=actor)
        if not slot.acquired:
            result = RateLimitResult(False, rule.policy, policy.concurrency.max, 0,
                                     slot.retry_after, slot.retry_after, "concurrency",
                                     "unavailable" if slot.degraded else "concurrency", slot.degraded)
            request._rl_last = request._rl_denied = result
            raise _error(result)

        request._rl_passed = True
        try:
            out = _next(root, info, *args, **kwargs)
        except BaseException:
            limiter.release_slot(slot.slot)
            raise
        if inspect.isawaitable(out):
            async def _await():
                try:
                    return await out
                finally:
                    limiter.release_slot(slot.slot)
            return _await()
        limiter.release_slot(slot.slot)
        return out
