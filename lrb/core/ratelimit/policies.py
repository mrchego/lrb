"""Every rate-limit rule is declared here, once, and validated when the app boots
(a bad policy stops the server from starting, the same rule as cache policies).

A *policy* is a set of *layers*. A request must pass every layer; tokens are only
spent if all layers agree. A layer's scope decides who is counted:

  ip       the client address (IPv6 grouped by /64)
  actor    the logged-in user, or the IP when anonymous
  company  everyone in the current company (fair use between tenants)
  subject  a value taken from the request arguments, e.g. the e-mail being logged into

Every key also contains the company id (or "platform"), so two companies can never
share a counter.

An *operation rule* maps a GraphQL root field to a policy and a cost.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from django.core.exceptions import ImproperlyConfigured

SCOPES = ("ip", "actor", "company", "subject")
FAILURE_MODES = ("open", "closed", "local")
_MAX_EXACT = 2**53  # Lua doubles are exact below this


@dataclass(frozen=True)
class TokenBucket:
    """`capacity` is the largest burst; `refill_tokens` come back every `refill_period` seconds."""
    capacity: int
    refill_tokens: int
    refill_period: int = 60


@dataclass(frozen=True)
class Window:
    """At most `limit` accepted requests in any rolling `seconds`."""
    limit: int
    seconds: int


@dataclass(frozen=True)
class Layer:
    scope: str
    rule: TokenBucket | Window


@dataclass(frozen=True)
class PenaltyRule:
    """Escalating blocks for repeated violations, keyed by IP. The score decays by 1
    every `decay_seconds`, so old behaviour is forgiven. ladder[k-1] is the block
    (seconds) at score k; the last entry applies to every higher score."""
    ladder: tuple[int, ...] = (0, 30, 120, 600)
    decay_seconds: float = 900.0


@dataclass(frozen=True)
class Concurrency:
    """At most `max` operations of this policy running at once per `scope`."""
    max: int
    lease_seconds: int = 120   # a crashed server's slot frees itself after this
    scope: str = "company"     # "company" | "actor"
    retry_after: int = 5


@dataclass(frozen=True)
class Policy:
    name: str
    layers: tuple[Layer, ...]
    failure: str = "local"     # Redis down: open = allow, closed = reject, local = per-process limiter
    penalty: PenaltyRule | None = None
    concurrency: Concurrency | None = None

    @property
    def algorithm(self) -> str:
        return "bucket" if isinstance(self.layers[0].rule, TokenBucket) else "window"


@dataclass(frozen=True)
class OperationRule:
    policy: str
    cost: int = 1
    subject: tuple[str, ...] | None = None  # path into the arguments, e.g. ("input", "email")


def B(capacity, refill, period=60):
    return TokenBucket(capacity, refill, period)


POLICIES: Mapping[str, Policy] = {
    p.name: p
    for p in (
        # Every HTTP request, checked before sessions or the database are touched.
        Policy("http", (Layer("ip", B(600, 600)), Layer("company", B(6000, 6000))), failure="local"),
        # Ordinary GraphQL traffic. Bursts allowed, long-run average enforced.
        Policy("api", (Layer("actor", B(100, 100)), Layer("company", B(2000, 2000))), failure="local"),
        # Expensive work: small burst, plus a cap on how many run at once.
        Policy(
            "heavy",
            (Layer("actor", B(10, 5)), Layer("company", B(60, 30))),
            failure="local",
            concurrency=Concurrency(max=3, lease_seconds=120, scope="company"),
        ),
        # Staff invitations send e-mail to arbitrary addresses.
        Policy("invite", (Layer("actor", B(20, 20, 3600)), Layer("company", B(100, 100, 3600))), failure="closed"),
        # Credential guessing. Sliding windows: no refill trick, no boundary burst.
        Policy(
            "login",
            (Layer("ip", Window(20, 60)), Layer("subject", Window(5, 60))),
            failure="local",
            penalty=PenaltyRule(),
        ),
        # Sends e-mail (cost + spam vector).
        Policy(
            "email_send",
            (Layer("ip", Window(10, 3600)), Layer("subject", Window(3, 3600))),
            failure="closed",
            penalty=PenaltyRule(),
        ),
        # Guessing 6-digit codes.
        Policy(
            "code_check",
            (Layer("ip", Window(20, 900)), Layer("subject", Window(5, 900))),
            failure="closed",
            penalty=PenaltyRule(),
        ),
        # Guessing the current password from an already-open session.
        Policy("password_change", (Layer("actor", Window(5, 900)), Layer("ip", Window(20, 900))), failure="closed"),
        # Creating companies.
        Policy("register", (Layer("ip", Window(5, 3600)),), failure="closed", penalty=PenaltyRule()),
    )
}

DEFAULT_QUERY = OperationRule("api", 1)
DEFAULT_MUTATION = OperationRule("api", 2)

_EMAIL = ("input", "email")

# GraphQL root-field name (camelCase, as in the schema) -> rule.
OPERATIONS: Mapping[str, OperationRule] = {
    "login": OperationRule("login", 1, _EMAIL),
    "forgotPassword": OperationRule("email_send", 1, _EMAIL),
    "requestEmailVerification": OperationRule("email_send", 1, _EMAIL),
    "verifyEmailCode": OperationRule("code_check", 1, _EMAIL),
    "resetPassword": OperationRule("code_check", 1, _EMAIL),
    "acceptInvitation": OperationRule("code_check", 1),
    "changePassword": OperationRule("password_change", 1),
    "registerCompany": OperationRule("register", 1),
    "inviteStaff": OperationRule("invite", 1),
    "resendInvitation": OperationRule("invite", 1),
    "dashboard": OperationRule("api", 5),
    **{
        name: OperationRule("heavy", 1)
        for name in (
            "bulkActivateProducts", "bulkActivateUsers", "bulkAssignRole",
            "bulkDeactivateProducts", "bulkDeactivateUsers", "bulkDeleteProduct",
            "bulkDeleteUsers", "bulkForcePasswordReset", "bulkLockUsers",
            "bulkRemoveRole", "bulkRestoreUsers", "bulkRevokeInvitations",
            "bulkUnlockUsers",
        )
    },
}

# Operations that MUST keep a strict rule. A test checks they still exist in the schema,
# so renaming `forgotPassword` cannot silently demote it to the generic policy.
STRICT_OPERATIONS = ("login", "forgotPassword", "requestEmailVerification",
                     "verifyEmailCode", "resetPassword", "changePassword", "registerCompany")


def rule_for(field_name: str, kind: str) -> OperationRule:
    rule = OPERATIONS.get(field_name)
    if rule is not None:
        return rule
    return DEFAULT_MUTATION if kind == "mutation" else DEFAULT_QUERY


def _bad(msg: str):
    raise ImproperlyConfigured(f"ratelimit policy error: {msg}")


def validate() -> None:
    for name, p in POLICIES.items():
        if name != p.name:
            _bad(f"{name}: key and name differ")
        if p.failure not in FAILURE_MODES:
            _bad(f"{name}: failure must be one of {FAILURE_MODES}")
        if not p.layers:
            _bad(f"{name}: needs at least one layer")
        kinds = {type(l.rule) for l in p.layers}
        if len(kinds) != 1:
            _bad(f"{name}: all layers must use the same algorithm")
        scopes = [l.scope for l in p.layers]
        if len(set(scopes)) != len(scopes) or any(s not in SCOPES for s in scopes):
            _bad(f"{name}: scopes must be unique and in {SCOPES}")
        for l in p.layers:
            r = l.rule
            if isinstance(r, TokenBucket):
                if min(r.capacity, r.refill_tokens, r.refill_period) < 1:
                    _bad(f"{name}/{l.scope}: bucket numbers must be >= 1")
                if r.capacity * 1000 * r.refill_period * 1_000_000 >= _MAX_EXACT:
                    _bad(f"{name}/{l.scope}: capacity x period too large for exact arithmetic")
            else:
                if r.limit < 1 or r.seconds < 1 or r.limit > 1000:
                    _bad(f"{name}/{l.scope}: window limit must be 1..1000 and seconds >= 1")
        if p.penalty and (not p.penalty.ladder or min(p.penalty.ladder) < 0 or p.penalty.decay_seconds <= 0):
            _bad(f"{name}: invalid penalty rule")
        if p.penalty and "ip" not in scopes:
            _bad(f"{name}: penalties are keyed by IP, so the policy needs an ip layer")
        if p.concurrency and (p.concurrency.max < 1 or p.concurrency.scope not in ("company", "actor")):
            _bad(f"{name}: invalid concurrency rule")
    for op, rule in [*OPERATIONS.items(), ("<default query>", DEFAULT_QUERY), ("<default mutation>", DEFAULT_MUTATION)]:
        p = POLICIES.get(rule.policy)
        if p is None:
            _bad(f"{op}: unknown policy {rule.policy!r}")
        if rule.cost < 1:
            _bad(f"{op}: cost must be >= 1")
        for l in p.layers:
            cap = l.rule.capacity if isinstance(l.rule, TokenBucket) else 1
            if rule.cost > cap:
                _bad(f"{op}: cost {rule.cost} exceeds capacity of {p.name}/{l.scope}; it could never succeed")
        if isinstance(p.layers[0].rule, Window) and rule.cost != 1:
            _bad(f"{op}: sliding-window policies only support cost 1")
    for op in STRICT_OPERATIONS:
        if op not in OPERATIONS:
            _bad(f"strict operation {op!r} has no rule")


validate()
