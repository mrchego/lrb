from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    policy: str
    limit: int = 0            # capacity / max requests of the deciding layer
    remaining: int = 0        # whole tokens / requests left in the deciding layer
    retry_after: int = 0      # whole seconds; 0 when allowed
    reset_after: int = 0      # seconds until that layer is fully available again
    layer: str | None = None  # which layer decided ("ip", "actor", ..., "penalty", "concurrency")
    reason: str = "ok"        # ok | limit | penalty | concurrency | unavailable | invalid_cost | shadow
    degraded: bool = False    # decided without Redis (fallback path)


ALLOWED_UNLIMITED = RateLimitResult(allowed=True, policy="none")
