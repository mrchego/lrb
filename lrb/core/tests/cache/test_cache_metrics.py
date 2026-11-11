import json
import logging

import pytest

from lrb.core.cache import metrics


@pytest.fixture(autouse=True)
def fresh():
    metrics.reset()
    yield
    metrics.reset()


def test_counts_accumulate_per_policy():
    metrics.record("p.one", "hit")
    metrics.record("p.one", "hit")
    metrics.record("p.one", "miss")
    metrics.record("p.two", "hit", 3)
    assert metrics.snapshot() == {"p.one": {"hit": 2, "miss": 1}, "p.two": {"hit": 3}}


def test_summary_line_is_logged_with_a_hit_ratio(monkeypatch, caplog):
    monkeypatch.setattr(metrics, "FLUSH_EVERY_EVENTS", 4)
    with caplog.at_level(logging.INFO, logger="lrb.core.cache.metrics"):
        for event in ("hit", "hit", "hit", "miss"):
            metrics.record("p.one", event)
    line = next(r.getMessage() for r in caplog.records if "cache_metrics" in r.getMessage())
    summary = json.loads(line.split("cache_metrics ", 1)[1])
    assert summary["p.one"]["hit_ratio"] == 0.75
    assert summary["p.one"]["hit"] == 3
    assert metrics.snapshot()["p.one"]["hit"] == 3  # cumulative counters survive the flush


def test_summary_is_also_logged_after_a_time_window(monkeypatch, caplog):
    now = [0.0]
    monkeypatch.setattr(metrics, "_clock", lambda: now[0])
    metrics.reset()
    with caplog.at_level(logging.INFO, logger="lrb.core.cache.metrics"):
        metrics.record("p.one", "hit")
        assert not caplog.records
        now[0] = 61.0
        metrics.record("p.one", "miss")
    assert any("cache_metrics" in r.getMessage() for r in caplog.records)
