"""JSON serializer for the shared Redis cache.

Django's Redis backend pickles values by default. Unpickling data that came
from a shared Redis means running whatever code that data describes, so anyone
who can write to Redis could run code inside the app. JSON can only ever
produce plain data (dicts, lists, strings, numbers, booleans, null).

Rule that follows: cache only JSON-friendly values. A `set` or a `Decimal`
raises TypeError on purpose; convert it in the caller (for example, store a
sorted list and turn it back into a set after reading).
"""
from __future__ import annotations

import json
from typing import Any


class JSONSerializer:
    def dumps(self, obj: Any) -> int | bytes:
        # Django relies on Redis storing plain integers for incr()/decr().
        # type() (not isinstance) so that bool is NOT treated as an int.
        if type(obj) is int:
            return obj
        return json.dumps(obj, separators=(",", ":"), allow_nan=False).encode("utf-8")

    def loads(self, data: bytes | int | str) -> Any:
        try:
            return int(data)
        except (TypeError, ValueError):
            return json.loads(data)
