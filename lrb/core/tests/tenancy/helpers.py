"""Helpers shared by the isolation tests: GraphQL literals, tenant-aware snapshots, attacks.

Rule for every snapshot ("watcher") helper: read a row INSIDE the schema it lives in.
Under schema-per-company, a row of company B simply does not exist in A's schema, so a
watcher that reads from the wrong schema would report 'DELETED' and mask a real attack.
"""
from __future__ import annotations

import json

from django_tenants.utils import tenant_context

from lrb.authorization.models.role import Role
from lrb.authorization.models.user_role import UserPermissionOverride, UserRole
from lrb.company.models.company import Company
from lrb.staff.models import Invitation

BULK = "success succeededIds"


# --------------------------------------------------------------------------- #
# GraphQL literal helpers                                                      #
# --------------------------------------------------------------------------- #
def lit(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(lit(v) for v in value) + "]"
    return json.dumps(str(value))


def mutation(operation: str, selection: str = "success", /, **input_fields) -> str:
    body = ", ".join(f"{k}: {lit(v)}" for k, v in input_fields.items())
    return f"mutation {{ {operation}(input: {{ {body} }}) {{ {selection} }} }}"


def succeeded(result, operation: str) -> bool:
    data = (result.data or {}).get(operation)
    if not data:
        return False
    if "succeededIds" in data:
        return bool(data["succeededIds"])
    return data.get("success") is True


def error_messages(result) -> list[str]:
    return [str(e.message) for e in (result.errors or [])]


# --------------------------------------------------------------------------- #
# Tenant-aware snapshots                                                       #
# --------------------------------------------------------------------------- #
def tenant_of(obj) -> Company:
    """The company whose schema holds this row."""
    return obj if isinstance(obj, Company) else obj.company


def state(obj, *fields):
    """Snapshot of a row, or 'DELETED' if it no longer exists in its own schema."""
    with tenant_context(tenant_of(obj)):
        try:
            obj.refresh_from_db()
        except obj.__class__.DoesNotExist:
            return "DELETED"
        return {f: getattr(obj, f) for f in fields}


USER_FIELDS = (
    "is_active", "can_login", "is_superuser", "is_staff", "locked_until",
    "failed_login_attempts", "password_reset_required", "first_name", "last_name",
)
PRODUCT_FIELDS = ("name", "sku", "price", "is_active")


def role_state(role):
    with tenant_context(tenant_of(role)):
        row = Role.objects.filter(pk=role.pk).first()
        return {
            "exists": row is not None,
            "name": row.name if row else None,
            "perms": sorted(row.permissions.values_list("codename", flat=True)) if row else None,
            "assigned": sorted(
                str(u) for u in UserRole.objects.filter(role_id=role.pk).values_list("user_id", flat=True)
            ),
        }


def user_roles_state(user):
    with tenant_context(tenant_of(user)):
        return {
            "roles": sorted(
                str(r) for r in UserRole.objects.filter(user=user).values_list("role_id", flat=True)
            ),
            "overrides": sorted(
                UserPermissionOverride.objects.filter(user=user).values_list(
                    "permission__codename", "is_granted"
                )
            ),
            "user": state(user, *USER_FIELDS),
        }


def count_in(company, model, **filters) -> int:
    with tenant_context(company):
        return model.objects.filter(**filters).count()


def count_everywhere(w, model, **filters) -> dict:
    """Same count in BOTH company schemas. An attack could create rows in either one:
    in A's (the attacker's own site) or in B's (when A's user is presented on B's host)."""
    return {"A": count_in(w.a, model, **filters), "B": count_in(w.b, model, **filters)}


def invitation_state(user, invitation):
    company = tenant_of(invitation)
    with tenant_context(company):
        from lrb.accounts.models import User

        return {
            "invitation": Invitation.objects.filter(pk=invitation.pk).values_list(
                "token", "expires_at", "used"
            ).first(),
            "user_exists": User.objects.filter(pk=user.pk).exists(),
        }


# --------------------------------------------------------------------------- #
# Attack registry                                                              #
# --------------------------------------------------------------------------- #
ATTACKS: list = []
PRODUCT_ATTACKS: list = []
COVERED: set[str] = set()

# Where the request arrives:
#   own_host    A's user on A's site. B's rows are not even in the active schema.
#   cross_host  A's user presented on B's site. B's rows ARE in the active schema, so only
#               the tenant guards (assert_user_in_current_tenant, company_id filters) stand
#               between the attacker and B's data. This is the position that matters most.
POSITIONS = ("own_host", "cross_host")


def host_for(w, position: str):
    return None if position == "own_host" else w.b


def attack(*operations, product: bool = False):
    def deco(fn):
        COVERED.update(operations)
        ATTACKS.append(fn)
        if product:
            PRODUCT_ATTACKS.append(fn)
        return fn

    return deco


def assert_attack_fails(w, actor, fn, *, position: str) -> None:
    document, operation, watcher = fn(w)
    before = watcher()
    result = w.run(actor, document, host=host_for(w, position))
    after = watcher()
    assert not succeeded(result, operation), f"{operation} [{position}]: cross-company attack reported success"
    assert after == before, f"{operation} [{position}]: company B's data was modified"