"""Rate-limit tests need a real Redis (the Lua scripts are the thing under test).
They use a DEDICATED database (RATE_LIMIT_TEST_REDIS_URL, default db 15) and flush it,
so never point that variable at a database you care about."""
import os

import django
import pytest
from django.conf import settings

TEST_URL = os.environ.get("RATE_LIMIT_TEST_REDIS_URL", "redis://redis:6379/15")



@pytest.fixture(autouse=True)
def rl(settings):
    import redis
    from lrb.core.ratelimit import metrics, store
    from lrb.core.ratelimit.local import local_buckets

    settings.RATE_LIMIT_REDIS_URL = TEST_URL
    settings.RATE_LIMIT_MODE = "enforce"
    settings.RATE_LIMIT_TRUSTED_PROXY_COUNT = 0
    store.reset_client()
    redis.Redis.from_url(TEST_URL).flushdb()
    local_buckets.clear()
    metrics.reset()
    yield
    store.reset_client()
