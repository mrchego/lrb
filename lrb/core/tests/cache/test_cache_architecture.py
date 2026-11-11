"""Rules that keep every app on the shared cache platform (like your permission-registry test)."""
import re
from pathlib import Path

import lrb

ROOT = Path(lrb.__file__).resolve().parent
CACHE_PACKAGE = ROOT / "core" / "cache"


def _production_files():
    for path in ROOT.rglob("*.py"):
        parts = set(path.relative_to(ROOT).parts)
        if parts & {"tests", "migrations"} or path.name == "conftest.py":
            continue
        if CACHE_PACKAGE in path.parents:
            continue
        yield path


def test_no_app_talks_to_django_cache_directly():
    offenders = [
        str(p.relative_to(ROOT))
        for p in _production_files()
        if re.search(r"^\s*(from|import)\s+django\.core\.cache", p.read_text(encoding="utf-8"), re.M)
    ]
    assert not offenders, (
        "Use lrb.core.cache (cached_read / cache_get / invalidate_policy) instead of "
        f"django.core.cache: {offenders}"
    )


def test_policies_are_only_declared_where_autodiscovery_looks():
    offenders = [
        str(p.relative_to(ROOT))
        for p in _production_files()
        if p.name != "cache_policies.py"
        and re.search(r"\bregister_policy\(", p.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"Move register_policy(...) into <app>/cache_policies.py: {offenders}"
