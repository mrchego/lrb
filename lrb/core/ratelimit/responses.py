from __future__ import annotations

import time

from lrb.core.exceptions import ErrorCode
from lrb.core.ratelimit.result import RateLimitResult


def message(result: RateLimitResult) -> str:
    if result.reason == "unavailable":
        return "This action is temporarily unavailable. Please try again shortly."
    if result.reason == "penalty":
        return f"Too many failed attempts. Try again in {result.retry_after} seconds."
    return f"Too many requests. Try again in {result.retry_after} seconds."


def graphql_errors(result: RateLimitResult) -> list[dict]:
    """Same shape the frontend's gqlFetch already reads (errors[0].extensions.code)."""
    return [{"message": message(result),
             "extensions": {"code": ErrorCode.RATE_LIMITED, "retryAfter": result.retry_after}}]


def headers(result: RateLimitResult) -> dict[str, str]:
    h = {}
    if result.limit:
        h["X-RateLimit-Limit"] = str(result.limit)
        h["X-RateLimit-Remaining"] = str(result.remaining)
        h["X-RateLimit-Reset"] = str(int(time.time()) + result.reset_after)
    if not result.allowed and result.retry_after:
        h["Retry-After"] = str(result.retry_after)
    return h
