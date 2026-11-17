"""Runs inside the lrb project (needs config.schema). Fails if a rule points at an
operation that no longer exists, e.g. after renaming `forgotPassword`: the rename would
otherwise silently demote it to the generic policy.

Operations live in two schemas: the tenant schema and the public/platform schema
(e.g. registerCompany), so a rule is valid if it exists in EITHER."""
from lrb.core.ratelimit.policies import OPERATIONS, STRICT_OPERATIONS


def _root_fields(schema):
    g = schema._schema
    names = set(g.query_type.fields)
    if g.mutation_type:
        names |= set(g.mutation_type.fields)
    return names


def _all_fields():
    from config.schema import schema
    from config.schema_public import schema as public
    return _root_fields(schema) | _root_fields(public)


def test_rules_point_at_real_operations():
    missing = [op for op in OPERATIONS if op not in _all_fields()]
    assert not missing, f"rules for operations that exist in no schema: {missing}"


def test_strict_operations_exist_in_schema():
    missing = set(STRICT_OPERATIONS) - _all_fields()
    assert not missing, f"strict operations missing from the schemas: {missing}"


def test_extension_is_installed_on_both_schemas():
    from config.schema import schema
    from config.schema_public import schema as public
    from lrb.core.ratelimit.graphql import RateLimitExtension
    for s in (schema, public):
        assert any(e is RateLimitExtension or isinstance(e, RateLimitExtension) for e in s.extensions)
