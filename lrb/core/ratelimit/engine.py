"""The rate-limiting engine. Middleware and GraphQL code only ever see RateLimitResult;
Redis, Lua and the algorithms stay in here.

    result = limiter.check("login", company=..., ip=..., subject="a@b.com")
"""
from __future__ import annotations

import logging
import math
import uuid
from contextlib import contextmanager
from dataclasses import dataclass

from django.conf import settings

from lrb.core.ratelimit import keys, metrics, store
from lrb.core.ratelimit.local import local_buckets
from lrb.core.ratelimit.policies import POLICIES, Policy, TokenBucket, Window
from lrb.core.ratelimit.result import ALLOWED_UNLIMITED, RateLimitResult

logger = logging.getLogger(__name__)

GRACE_MS = 60_000
_US = 1_000_000


def mode() -> str:
    m = getattr(settings, "RATE_LIMIT_MODE", "enforce")
    return m if m in ("enforce", "shadow", "off") else "enforce"


def _secs(us: int) -> int:
    return max(1, math.ceil(us / _US)) if us > 0 else 0


@dataclass(frozen=True)
class Slot:
    key: str
    token: str


@dataclass(frozen=True)
class SlotResult:
    acquired: bool
    slot: Slot | None = None
    retry_after: int = 0
    degraded: bool = False


class RateLimiter:
    # ---- identities ---------------------------------------------------------
    def _layer_keys(self, kind, policy: Policy, company, ip, actor, subject):
        out = []
        for layer in policy.layers:
            if layer.scope == "ip":
                ident = keys.hash_identity(ip)
            elif layer.scope == "actor":
                ident = actor or ("a-" + keys.hash_identity(ip))
            elif layer.scope == "company":
                ident = "all"
            else:  # subject
                if not subject:
                    continue  # nothing to count, the ip layer still applies
                ident = keys.hash_identity(subject)
            out.append((layer, keys.build(kind, company, policy.name, layer.scope, ident)))
        return out

    # ---- public API ---------------------------------------------------------
    def check(self, policy_name: str, *, company: str, ip: str, actor: str | None = None,
              subject: str | None = None, cost: int = 1) -> RateLimitResult:
        m = mode()
        if m == "off":
            return ALLOWED_UNLIMITED
        policy = POLICIES[policy_name]
        if not isinstance(cost, int) or isinstance(cost, bool) or cost < 1:
            logger.error("rate limit: invalid cost %r for %s", cost, policy_name)
            return RateLimitResult(False, policy_name, reason="invalid_cost")

        result = self._decide(policy, company, ip, actor, subject, cost)
        if not result.allowed and m == "shadow":
            metrics.record(policy_name, "shadow_rejected")
            return RateLimitResult(True, policy_name, result.limit, result.remaining, 0,
                                   result.reset_after, result.layer, "shadow", result.degraded)
        metrics.record(policy_name, "allowed" if result.allowed else "rejected")
        return result

    # ---- decision -----------------------------------------------------------
    def _decide(self, policy, company, ip, actor, subject, cost) -> RateLimitResult:
        kind = "b" if policy.algorithm == "bucket" else "w"
        layers = self._layer_keys(kind, policy, company, ip, actor, subject)
        if not layers:
            return ALLOWED_UNLIMITED

        penalty_key = None
        if policy.penalty and ip != "unknown":
            penalty_key = keys.build("p", company, policy.name, "ip", keys.hash_identity(ip))

        try:
            if penalty_key:
                blocked, retry_us = store.run("PENALTY_CHECK", [penalty_key], [], policy=policy.name)
                if blocked:
                    metrics.record(policy.name, "penalty_blocked")
                    s = _secs(retry_us)
                    return RateLimitResult(False, policy.name, 0, 0, s, s, "penalty", "penalty")
            result = (self._bucket(policy, layers, cost) if kind == "b"
                      else self._window(policy, layers))
            if not result.allowed and penalty_key:
                self._violate(policy, penalty_key)
            return result
        except store.StoreUnavailable:
            return self._fallback(policy, layers, cost)

    def _bucket(self, policy, layers, cost) -> RateLimitResult:
        args: list = [len(layers), GRACE_MS]
        for layer, _ in layers:
            r: TokenBucket = layer.rule
            args += [r.capacity * 1000, r.refill_tokens * 1000, r.refill_period * _US, cost * 1000]
        out = store.run("TOKEN_BUCKET", [k for _, k in layers], args, policy=policy.name)
        return self._parse(policy, layers, out, milli=True)

    def _window(self, policy, layers) -> RateLimitResult:
        args: list = [len(layers), uuid.uuid4().hex, GRACE_MS]
        for layer, _ in layers:
            r: Window = layer.rule
            args += [r.limit, r.seconds * _US]
        out = store.run("SLIDING_WINDOW", [k for _, k in layers], args, policy=policy.name)
        return self._parse(policy, layers, out, milli=False)

    @staticmethod
    def _parse(policy, layers, out, *, milli: bool) -> RateLimitResult:
        allowed, binding = bool(out[0]), int(out[1])
        rows = [(int(out[2 + i * 3]), int(out[3 + i * 3]), int(out[4 + i * 3])) for i in range(len(layers))]

        def cap(layer):
            return layer.rule.capacity if isinstance(layer.rule, TokenBucket) else layer.rule.limit

        def remaining(i):
            r = rows[i][0]
            return max(0, r // 1000 if milli else r)

        if not allowed:
            i = binding - 1
            return RateLimitResult(False, policy.name, cap(layers[i][0]), remaining(i),
                                   _secs(rows[i][1]), _secs(rows[i][2]), layers[i][0].scope, "limit")
        # allowed: report the layer closest to running out
        i = min(range(len(layers)), key=lambda j: rows[j][0] / (cap(layers[j][0]) * (1000 if milli else 1)))
        return RateLimitResult(True, policy.name, cap(layers[i][0]), remaining(i), 0,
                               _secs(rows[i][2]), layers[i][0].scope, "ok")

    def _violate(self, policy, penalty_key) -> None:
        p = policy.penalty
        try:
            _, secs = store.run("PENALTY_VIOLATE", [penalty_key],
                                [repr(1.0 / p.decay_seconds), GRACE_MS, *p.ladder], policy=policy.name)
            if secs:
                metrics.record(policy.name, "penalty_applied")
        except store.StoreUnavailable:
            pass  # best effort: the rejection itself already happened

    # ---- Redis unavailable --------------------------------------------------
    def _fallback(self, policy, layers, cost) -> RateLimitResult:
        if policy.failure == "open":
            metrics.record(policy.name, "fallback_open")
            return RateLimitResult(True, policy.name, reason="unavailable", degraded=True)
        if policy.failure == "closed":
            metrics.record(policy.name, "fallback_closed")
            return RateLimitResult(False, policy.name, retry_after=int(store.breaker._cooldown) or 5,
                                   reason="unavailable", degraded=True)
        metrics.record(policy.name, "fallback_local")
        items = []
        for layer, key in layers:
            r = layer.rule
            if isinstance(r, TokenBucket):
                items.append((key, r.capacity, r.refill_tokens / r.refill_period, cost))
            else:
                items.append((key, r.limit, r.limit / r.seconds, 1))
        ok, retry = local_buckets.check(items)
        return RateLimitResult(ok, policy.name, retry_after=0 if ok else max(1, math.ceil(retry)),
                               reason="ok" if ok else "limit", degraded=True)

    # ---- concurrency ----------------------------------------------------------
    def acquire_slot(self, policy_name: str, *, company: str, actor: str | None) -> SlotResult:
        policy = POLICIES[policy_name]
        c = policy.concurrency
        if c is None or mode() == "off":
            return SlotResult(True)
        ident = (actor or "anon") if c.scope == "actor" else "all"
        key = keys.build("c", company, policy.name, c.scope, ident)
        token = uuid.uuid4().hex
        try:
            ok, _ = store.run("SEM_ACQUIRE", [key], [c.max, c.lease_seconds * _US, token, GRACE_MS],
                              policy=policy.name)
        except store.StoreUnavailable:
            if policy.failure == "closed":
                return SlotResult(False, retry_after=c.retry_after, degraded=True)
            return SlotResult(True, degraded=True)  # rate buckets (local fallback) still protect
        if ok:
            return SlotResult(True, Slot(key, token))
        metrics.record(policy.name, "concurrency_rejected")
        if mode() == "shadow":
            return SlotResult(True)
        return SlotResult(False, retry_after=c.retry_after)

    def release_slot(self, slot: Slot | None) -> None:
        if slot is None:
            return
        try:
            store.run("SEM_RELEASE", [slot.key], [slot.token])
        except store.StoreUnavailable:
            pass  # the lease expires on its own

    @contextmanager
    def concurrency_slot(self, policy_name: str, *, company: str, actor: str | None):
        res = self.acquire_slot(policy_name, company=company, actor=actor)
        try:
            yield res
        finally:
            self.release_slot(res.slot)


limiter = RateLimiter()
