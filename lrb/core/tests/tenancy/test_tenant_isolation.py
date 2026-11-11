"""
Cross-company isolation suite for the schema-per-company design.

What "isolation" means now, in three layers:
  1. The database layer. Each company lives in its own PostgreSQL schema, so company B's
     rows are not even visible from A's schema (see test_schema_isolation.py).
  2. The guard layer. assert_user_in_current_tenant / require_company_id / company_id
     filters decide what happens when a user is presented on the wrong site, or when there
     is no company context at all.
  3. The application layer (this file): every id-taking operation is attacked from BOTH
     positions and must fail, leaving B's data byte-for-byte unchanged:
        own_host    A's user on A's site: B's ids point at nothing in the active schema.
        cross_host  A's user on B's site: B's rows are in the active schema, so only the
                    guards stand in the way. This is the dangerous case.

Plus a COVERAGE GUARD: fails if the schema gains an id-taking operation with no attack.

To add an attack: write a function returning (graphql_document, operation_name, watcher)
and decorate it with @attack("operationName"). `watcher()` returns the target's state and
must be equal before and after. Read state ONLY through the helpers in helpers.py (they
enter the right schema); count rows with count_everywhere() so a row created in either
company's schema is noticed.
"""
from __future__ import annotations

import inspect
import re

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.utils import timezone
from django_tenants.utils import tenant_context
from graphql import GraphQLInputObjectType, get_named_type

from config.schema import schema
from lrb.accounts.models import User
from lrb.accounts.selectors.get_user import get_user
from lrb.accounts.selectors.get_users_by_ids import get_users_by_ids
from lrb.accounts.selectors.list_users import list_users
from lrb.accounts.services.promote_to_owner import promote_to_owner
from lrb.accounts.services.update_user import update_user
from lrb.authorization.models.permission import Permission
from lrb.authorization.models.role import Role
from lrb.authorization.models.user_role import UserPermissionOverride, UserRole
from lrb.authorization.permissions import PERMISSION_REGISTRY
from lrb.authorization.selectors.get_role import get_role
from lrb.authorization.selectors.get_user_permissions import get_user_permission_codenames
from lrb.authorization.selectors.user_has_permission import user_has_permission
from lrb.core.exceptions import AppPermissionDeniedError, ApplicationError
from lrb.identity.services.login import login
from lrb.products.selectors.get_product import get_product
from lrb.products.selectors.get_products_by_ids import get_products_by_ids
from lrb.products.selectors.list_products import list_products
from lrb.staff.models import Invitation

from .conftest import PASSWORD
from .helpers import (
    ATTACKS, BULK, COVERED, POSITIONS, PRODUCT_ATTACKS, PRODUCT_FIELDS, USER_FIELDS,
    assert_attack_fails, attack, count_everywhere, invitation_state, mutation, role_state,
    state, succeeded, user_roles_state,
)

pytestmark = pytest.mark.django_db


def _update_user(company, user, **fields):
    """Direct write to a user's row, inside that company's own schema."""
    with tenant_context(company):
        User.objects.filter(pk=user.pk).update(**fields)


# ----- products (run as A's owner AND as A's permission-holding staff) -------
@attack("updateProduct", product=True)
def atk_update_product(w):
    p = w.new_product(w.b)
    doc = mutation("updateProduct", productId=p.id, name="HACKED", isActive=False)
    return doc, "updateProduct", lambda: state(p, *PRODUCT_FIELDS)


@attack("deleteProduct", product=True)
def atk_delete_product(w):
    p = w.new_product(w.b)
    return mutation("deleteProduct", productId=p.id), "deleteProduct", lambda: state(p, *PRODUCT_FIELDS)


@attack("activateProduct", product=True)
def atk_activate_product(w):
    p = w.new_product(w.b, is_active=False)
    return mutation("activateProduct", productId=p.id), "activateProduct", lambda: state(p, *PRODUCT_FIELDS)


@attack("deactivateProduct", product=True)
def atk_deactivate_product(w):
    p = w.new_product(w.b, is_active=True)
    return mutation("deactivateProduct", productId=p.id), "deactivateProduct", lambda: state(p, *PRODUCT_FIELDS)


@attack("bulkActivateProducts", product=True)
def atk_bulk_activate_products(w):
    p = w.new_product(w.b, is_active=False)
    return (mutation("bulkActivateProducts", BULK, productIds=[p.id]),
            "bulkActivateProducts", lambda: state(p, *PRODUCT_FIELDS))


@attack("bulkDeactivateProducts", product=True)
def atk_bulk_deactivate_products(w):
    p = w.new_product(w.b, is_active=True)
    return (mutation("bulkDeactivateProducts", BULK, productIds=[p.id]),
            "bulkDeactivateProducts", lambda: state(p, *PRODUCT_FIELDS))


@attack("bulkDeleteProduct", product=True)
def atk_bulk_delete_product(w):
    p = w.new_product(w.b)
    return (mutation("bulkDeleteProduct", BULK, productIds=[p.id]),
            "bulkDeleteProduct", lambda: state(p, *PRODUCT_FIELDS))


# ----- users ------------------------------------------------------------------
@attack("adminUpdateUser")
def atk_admin_update_user(w):
    u = w.new_user(w.b)
    return (mutation("adminUpdateUser", userId=u.id, firstName="HACKED", lastName="HACKED"),
            "adminUpdateUser", lambda: state(u, *USER_FIELDS))


@attack("activateUser")
def atk_activate_user(w):
    u = w.new_user(w.b, is_active=False)
    return mutation("activateUser", userId=u.id), "activateUser", lambda: state(u, *USER_FIELDS)


@attack("deactivateUser")
def atk_deactivate_user(w):
    u = w.new_user(w.b)
    return mutation("deactivateUser", userId=u.id), "deactivateUser", lambda: state(u, *USER_FIELDS)


@attack("deleteUser")
def atk_delete_user(w):
    u = w.new_user(w.b)
    return mutation("deleteUser", userId=u.id), "deleteUser", lambda: state(u, *USER_FIELDS)


@attack("lockUser")
def atk_lock_user(w):
    u = w.new_user(w.b)
    return mutation("lockUser", userId=u.id, durationMinutes=60), "lockUser", lambda: state(u, *USER_FIELDS)


@attack("unlockUser")
def atk_unlock_user(w):
    u = w.new_user(w.b)
    _update_user(w.b, u, locked_until=timezone.now() + timezone.timedelta(hours=1), failed_login_attempts=4)
    return mutation("unlockUser", userId=u.id), "unlockUser", lambda: state(u, *USER_FIELDS)


@attack("forcePasswordReset")
def atk_force_password_reset(w):
    u = w.new_user(w.b)
    return mutation("forcePasswordReset", userId=u.id), "forcePasswordReset", lambda: state(u, *USER_FIELDS)


@attack("restoreUser")
def atk_restore_user(w):
    u = w.new_user(w.b, is_active=False, can_login=False)
    return mutation("restoreUser", userId=u.id), "restoreUser", lambda: state(u, *USER_FIELDS)


@attack("promoteToOwner")
def atk_promote_to_owner(w):
    u = w.new_user(w.b)
    return mutation("promoteToOwner", userId=u.id), "promoteToOwner", lambda: state(u, *USER_FIELDS)


@attack("demoteOwner")
def atk_demote_owner(w):
    # Non-founder owner on purpose: founder protection would otherwise mask the hole.
    u = w.new_user(w.b, is_superuser=True)
    return mutation("demoteOwner", userId=u.id), "demoteOwner", lambda: state(u, *USER_FIELDS)


def _bulk_user_attack(name, **extra):
    def fn(w):
        u = w.new_user(w.b)
        if name == "bulkUnlockUsers":
            _update_user(w.b, u, locked_until=timezone.now() + timezone.timedelta(hours=1), failed_login_attempts=4)
        if name == "bulkActivateUsers":
            _update_user(w.b, u, is_active=False)
        if name == "bulkRestoreUsers":
            _update_user(w.b, u, is_active=False, can_login=False)
        return (mutation(name, BULK, userIds=[u.id], **extra), name, lambda: state(u, *USER_FIELDS))

    fn.__name__ = f"atk_{name}"
    return attack(name)(fn)


for _name in (
    "bulkActivateUsers", "bulkDeactivateUsers", "bulkDeleteUsers", "bulkUnlockUsers",
    "bulkForcePasswordReset", "bulkRestoreUsers",
):
    _bulk_user_attack(_name)
_bulk_user_attack("bulkLockUsers", durationMinutes=60)


# ----- roles / permission overrides ------------------------------------------
@attack("updateRole")
def atk_update_role(w):
    r = w.new_role(w.b, ["products.view_product"])
    return (mutation("updateRole", roleId=r.id, name="HACKED", permissionCodenames=[]),
            "updateRole", lambda: role_state(r))


@attack("deleteRole")
def atk_delete_role(w):
    r = w.new_role(w.b, ["products.view_product"])
    return mutation("deleteRole", roleId=r.id), "deleteRole", lambda: role_state(r)


@attack("cloneRole")
def atk_clone_role(w):
    # A successful clone would COPY B's role into A and leak its permission set.
    r = w.new_role(w.b, ["products.view_product"])
    return (mutation("cloneRole", roleId=r.id, newName="stolen"), "cloneRole",
            lambda: {"roles": count_everywhere(w, Role), "b": role_state(r)})


@attack("assignRole")
def atk_assign_role_foreign_user_own_role(w):
    u = w.new_user(w.b)
    return (mutation("assignRole", userId=u.id, roleId=w.role_a.id), "assignRole",
            lambda: user_roles_state(u))


@attack("assignRole")
def atk_assign_role_own_user_foreign_role(w):
    return (mutation("assignRole", userId=w.staff_a.id, roleId=w.role_b.id), "assignRole",
            lambda: {"mine": user_roles_state(w.staff_a), "role": role_state(w.role_b)})


@attack("assignRole")
def atk_assign_role_foreign_both(w):
    u = w.new_user(w.b)
    return (mutation("assignRole", userId=u.id, roleId=w.role_b.id), "assignRole",
            lambda: {"u": user_roles_state(u), "role": role_state(w.role_b)})


@attack("removeRole")
def atk_remove_role(w):
    u = w.new_user(w.b, role=w.role_b)
    return (mutation("removeRole", userId=u.id, roleId=w.role_b.id), "removeRole",
            lambda: user_roles_state(u))


@attack("bulkAssignRole")
def atk_bulk_assign_foreign_user_own_role(w):
    u = w.new_user(w.b)
    return (mutation("bulkAssignRole", BULK, userIds=[u.id], roleId=w.role_a.id),
            "bulkAssignRole", lambda: user_roles_state(u))


@attack("bulkAssignRole")
def atk_bulk_assign_own_user_foreign_role(w):
    return (mutation("bulkAssignRole", BULK, userIds=[w.staff_a.id], roleId=w.role_b.id),
            "bulkAssignRole", lambda: {"mine": user_roles_state(w.staff_a), "role": role_state(w.role_b)})


@attack("bulkRemoveRole")
def atk_bulk_remove_role(w):
    u = w.new_user(w.b, role=w.role_b)
    return (mutation("bulkRemoveRole", BULK, userIds=[u.id], roleId=w.role_b.id),
            "bulkRemoveRole", lambda: user_roles_state(u))


@attack("setPermissionOverride")
def atk_set_permission_override(w):
    u = w.new_user(w.b)
    return (mutation("setPermissionOverride", userId=u.id,
                     permissionCodename="products.delete_product", isGranted=True),
            "setPermissionOverride", lambda: user_roles_state(u))


@attack("clearPermissionOverride")
def atk_clear_permission_override(w):
    from lrb.authorization.models.permission import Permission

    u = w.new_user(w.b)
    with tenant_context(w.b):
        UserPermissionOverride.objects.create(
            user=u, permission=Permission.objects.get(codename="products.view_product"), is_granted=False
        )
    return (mutation("clearPermissionOverride", userId=u.id,
                     permissionCodename="products.view_product"),
            "clearPermissionOverride", lambda: user_roles_state(u))


# ----- staff / invitations ----------------------------------------------------
@attack("revokeInvitation")
def atk_revoke_invitation(w):
    u, inv = w.new_invitation(w.b, w.owner_b)
    return mutation("revokeInvitation", invitationId=inv.id), "revokeInvitation", lambda: invitation_state(u, inv)


@attack("resendInvitation")
def atk_resend_invitation(w):
    u, inv = w.new_invitation(w.b, w.owner_b)
    return mutation("resendInvitation", invitationId=inv.id), "resendInvitation", lambda: invitation_state(u, inv)


@attack("bulkRevokeInvitations")
def atk_bulk_revoke_invitations(w):
    u, inv = w.new_invitation(w.b, w.owner_b)
    return (mutation("bulkRevokeInvitations", BULK, invitationIds=[inv.id]),
            "bulkRevokeInvitations", lambda: invitation_state(u, inv))


@attack("setStaffLoginAccess")
def atk_set_staff_login_access(w):
    u = w.new_user(w.b, role=w.role_b)
    return (mutation("setStaffLoginAccess", userId=u.id, canLogin=False),
            "setStaffLoginAccess", lambda: user_roles_state(u))


@attack("demoteStaffFromLogin")
def atk_demote_staff_from_login(w):
    u = w.new_user(w.b, role=w.role_b)
    return mutation("demoteStaffFromLogin", userId=u.id), "demoteStaffFromLogin", lambda: user_roles_state(u)


@attack("promoteStaffToLogin")
def atk_promote_staff_to_login(w):
    u = w.new_user(w.b, can_login=False)
    return (mutation("promoteStaffToLogin", userId=u.id, roleId=w.role_a.id),
            "promoteStaffToLogin",
            lambda: {"u": user_roles_state(u),
                     "invites": count_everywhere(w, Invitation, email=u.email)})


@attack("inviteStaff")
def atk_invite_staff_with_foreign_role(w):
    email = f"victim-{w.role_b.id.hex[:8]}@example.test"
    return (mutation("inviteStaff", email=email, firstName="X", lastName="Y",
                     canLogin=True, roleId=w.role_b.id),
            "inviteStaff",
            lambda: {"users": count_everywhere(w, User, email=email),
                     "invites": count_everywhere(w, Invitation, email=email),
                     "b_assigned": role_state(w.role_b)})


# --------------------------------------------------------------------------- #
# 1. WRITE attacks                                                             #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("position", POSITIONS)
@pytest.mark.parametrize("fn", ATTACKS, ids=lambda f: f.__name__)
def test_owner_of_A_cannot_touch_B(w, fn, position):
    assert_attack_fails(w, w.owner_a, fn, position=position)


@pytest.mark.parametrize("position", POSITIONS)
@pytest.mark.parametrize("fn", PRODUCT_ATTACKS, ids=lambda f: f.__name__)
def test_permission_holding_staff_of_A_cannot_touch_B_products(w, fn, position):
    # Permission to edit products means "in MY company", never "anywhere".
    assert_attack_fails(w, w.staff_a, fn, position=position)


def test_positive_control_own_company_still_works(w):
    """If everything errored for everyone, the attack tests above would pass
    vacuously. Prove the legitimate path works, in BOTH companies."""
    r = w.run(w.owner_a, mutation("updateProduct", productId=w.product_a.id, name="Renamed"))
    assert succeeded(r, "updateProduct")
    with tenant_context(w.a):
        w.product_a.refresh_from_db()
    assert w.product_a.name == "Renamed"

    r = w.run(w.staff_a, mutation("deactivateProduct", productId=w.product_a.id))
    assert succeeded(r, "deactivateProduct")
    with tenant_context(w.a):
        w.product_a.refresh_from_db()
    assert w.product_a.is_active is False

    own = w.new_user(w.a)
    r = w.run(w.owner_a, mutation("assignRole", userId=own.id, roleId=w.role_a.id))
    assert succeeded(r, "assignRole")
    with tenant_context(w.a):
        assert UserRole.objects.filter(user=own, role=w.role_a).exists()

    r = w.run(w.owner_a, mutation("lockUser", userId=own.id, durationMinutes=30))
    assert succeeded(r, "lockUser")

    # Company B's owner works on B's own site: so a failure above is never "B is broken".
    r = w.run(w.owner_b, mutation("updateProduct", productId=w.product_b.id, name="B-Renamed"))
    assert succeeded(r, "updateProduct")


# --------------------------------------------------------------------------- #
# 2. READ attacks                                                              #
# --------------------------------------------------------------------------- #
READ_COVERED = {"user", "product", "role", "effectivePermissions", "userPermissionOverrides"}


def _ids(result, path):
    assert not result.errors, result.errors
    node = result.data
    for key in path:
        node = node[key]
    return {n["id"] for n in node}


def test_users_list_only_returns_own_company(w):
    other = w.new_user(w.b)
    r = w.run(w.owner_a, "{ users(limit: 100) { items { id } totalCount } }")
    assert _ids(r, ["users", "items"]) == {str(w.owner_a.id), str(w.staff_a.id)}
    assert str(other.id) not in _ids(r, ["users", "items"])


def test_user_by_id_of_other_company_is_null(w):
    r = w.run(w.owner_a, f'{{ user(userId: "{w.staff_b.id}") {{ id email }} }}')
    assert (r.data or {}).get("user") is None


def test_products_list_only_returns_own_company(w):
    r = w.run(w.owner_a, "{ products(limit: 100) { items { id } totalCount } }")
    assert _ids(r, ["products", "items"]) == {str(w.product_a.id)}
    r = w.run(w.staff_a, "{ products(limit: 100) { items { id } } }")
    assert _ids(r, ["products", "items"]) == {str(w.product_a.id)}


def test_product_by_id_of_other_company_is_null(w):
    q = f'{{ product(input: {{ productId: "{w.product_b.id}" }}) {{ id }} }}'
    assert (w.run(w.owner_a, q).data or {}).get("product") is None
    assert (w.run(w.staff_a, q).data or {}).get("product") is None


def test_roles_list_only_returns_own_company(w):
    r = w.run(w.owner_a, "{ roles { id } }")
    assert _ids(r, ["roles"]) == {str(w.role_a.id)}


def test_role_by_id_of_other_company_is_null(w):
    r = w.run(w.owner_a, f'{{ role(roleId: "{w.role_b.id}") {{ id }} }}')
    assert (r.data or {}).get("role") is None


def test_effective_permissions_of_foreign_user_is_empty(w):
    r = w.run(w.owner_a, f'{{ effectivePermissions(userId: "{w.staff_b.id}") {{ codenames }} }}')
    assert not r.errors
    assert r.data["effectivePermissions"]["codenames"] == []


def test_permission_overrides_of_foreign_user_is_empty(w):
    with tenant_context(w.b):
        UserPermissionOverride.objects.create(
            user=w.staff_b, permission=Permission.objects.get(codename="products.view_product")
        )
    r = w.run(w.owner_a, f'{{ userPermissionOverrides(userId: "{w.staff_b.id}") {{ __typename }} }}')
    assert not r.errors
    assert r.data["userPermissionOverrides"] == []


def test_invitations_and_staff_lists_only_return_own_company(w):
    _, inv_b = w.new_invitation(w.b, w.owner_b)
    _, inv_a = w.new_invitation(w.a, w.owner_a)
    r = w.run(w.owner_a, "{ invitations(limit: 100) { items { id } } }")
    ids = _ids(r, ["invitations", "items"])
    assert str(inv_a.id) in ids and str(inv_b.id) not in ids
    r = w.run(w.owner_a, "{ staffMembers(limit: 100) { items { id } } }")
    assert str(w.staff_b.id) not in _ids(r, ["staffMembers", "items"])


def test_company_query_returns_own_company_only(w):
    r = w.run(w.owner_a, "{ company { name } }")
    assert r.data["company"]["name"] == w.a.name


# --------------------------------------------------------------------------- #
# 3. Structural / defence-in-depth                                             #
# --------------------------------------------------------------------------- #
def test_selectors_fail_closed_without_company(w):
    for call in (
        lambda: get_user(user_id=w.staff_a.id, company_id=None),
        lambda: get_users_by_ids(user_ids=[w.staff_a.id], company_id=""),
        lambda: list_users(company_id=None),
        lambda: get_role(role_id=w.role_a.id, company_id=None),
        lambda: get_product(product_id=w.product_a.id, company_id=None),
        lambda: get_products_by_ids(product_ids=[w.product_a.id], company_id=None),
        lambda: list_products(company_id=None),
    ):
        with pytest.raises(AppPermissionDeniedError):
            call()


def test_deactivated_company_loses_all_access(w):
    w.a.is_active = False
    w.a.save(update_fields=["is_active"])
    # a live session: the user is loaded fresh from the DB on every request
    with tenant_context(w.a):
        session_user = User.objects.get(pk=w.owner_a.pk)
    r = w.run(session_user, "{ products { items { id } } }")
    assert r.errors
    r = w.run(session_user, "{ dashboard { __typename } }")
    assert r.errors
    # new sign-in
    with tenant_context(w.a):
        with pytest.raises(ApplicationError):
            login(email=w.owner_a.email, password=PASSWORD)


def test_cross_company_userrole_cannot_be_saved(w):
    with tenant_context(w.a):
        with pytest.raises(ValidationError):
            UserRole.objects.create(user=w.staff_a, role=w.role_b)


def test_cross_company_userrole_is_physically_impossible(w):
    """The old test bypassed the model guard with bulk_create. Now the DATABASE refuses:
    company B's role is not a row in A's schema, so the foreign key cannot be satisfied."""
    loner = w.new_user(w.a)
    with tenant_context(w.a):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                UserRole.objects.bulk_create([UserRole(user=loner, role=w.role_b)])
                connection.check_constraints()  # foreign keys are deferred: force the check now


def test_a_foreign_role_inside_A_never_grants_permissions(w):
    """Defence in depth. Schema isolation makes it hard to even get B's role next to A's
    user, but a role row that CLAIMS company B and sits inside A's schema is physically
    possible. The permission selector must still ignore it."""
    with tenant_context(w.a):
        alien = Role.objects.create(company=w.b, name="alien-role")
        alien.permissions.add(Permission.objects.get(codename="products.delete_product"))
    loner = w.new_user(w.a)  # no roles of their own
    with tenant_context(w.a):
        # Bypass the model guard on purpose: bulk_create never calls save().
        UserRole.objects.bulk_create([UserRole(user=loner, role=alien)])
        from django.core.cache import cache

        cache.clear()
        assert "products.delete_product" not in get_user_permission_codenames(user=loner)
        assert not user_has_permission(user=loner, codename="products.delete_product")


def test_invitation_role_must_match_company(w):
    from datetime import timedelta

    with tenant_context(w.a):
        with pytest.raises(ValidationError):
            Invitation.objects.create(
                email="x@example.test", company=w.a, invited_by=w.owner_a,
                role=w.role_b, expires_at=timezone.now() + timedelta(days=1),
            )


def test_update_user_cannot_move_a_user_between_companies():
    assert "company" not in inspect.signature(update_user).parameters


def test_promoting_to_owner_never_grants_django_admin_access(w):
    u = w.new_user(w.a)
    with tenant_context(w.a):
        promote_to_owner(user_id=u.id, company_id=str(w.a.id))
        u.refresh_from_db()
    assert u.is_superuser is True and u.is_staff is False


def test_another_companys_user_emails_are_invisible_from_this_schema(w):
    """REPLACES test_invite_does_not_reveal_emails_from_other_companies.

    The old test asserted that inviting an email that exists in another company gave the
    SAME error as inviting an existing colleague (so duplicates could not be used to probe
    other companies). With a schema per company, other companies' users are not even in the
    schema being searched, so there is nothing to probe: the lookup finds nothing.

    Whether the same email address may belong to users of two companies is a PRODUCT
    decision. If it must stay forbidden, that needs an explicit platform-level check, and
    this test should grow a second assertion for it."""
    with tenant_context(w.a):
        assert not User.objects.filter(email=w.staff_b.email).exists()
        assert User.objects.filter(email=w.staff_a.email).exists()  # same-company still found


# --------------------------------------------------------------------------- #
# 4. COVERAGE GUARD                                                            #
# --------------------------------------------------------------------------- #
_ID_NAME = re.compile(r"(Id|Ids)$")


def _id_taking_operations(root_type) -> set[str]:
    found = set()
    for op_name, field in root_type.fields.items():
        for arg_name, arg in field.args.items():
            named = get_named_type(arg.type)
            if _ID_NAME.search(arg_name):
                found.add(op_name)
            elif isinstance(named, GraphQLInputObjectType) and any(
                _ID_NAME.search(f) for f in named.fields
            ):
                found.add(op_name)
    return found


def test_every_id_taking_operation_has_a_cross_company_test():
    gschema = schema._schema
    missing_mutations = _id_taking_operations(gschema.mutation_type) - COVERED
    missing_queries = _id_taking_operations(gschema.query_type) - READ_COVERED
    assert not missing_mutations, (
        f"Mutations taking an id with NO cross-company attack: {sorted(missing_mutations)}. "
        "Add an @attack(...) for each."
    )
    assert not missing_queries, (
        f"Queries taking an id with NO cross-company read test: {sorted(missing_queries)}. "
        "Add a read test and register the name in READ_COVERED."
    )


def test_every_permission_string_used_in_resolvers_exists_in_the_registry():
    """Catches the 'activate_product' vs 'products.activate_product' class of typo:
    a resolver guarded by a codename that is not in PERMISSION_REGISTRY would be
    unreachable for every non-owner and silently owner-only."""
    import lrb.products.graphql.mutations as m
    import lrb.products.graphql.queries as q

    registry = {codename for codename, _, _ in PERMISSION_REGISTRY}
    used = set()
    for module in (m, q):
        used |= set(re.findall(r'require_permission\("([^"]+)"\)', inspect.getsource(module)))
    assert used, "no require_permission(...) strings found - regex out of date?"
    assert used <= registry, f"unknown permission codenames in resolvers: {sorted(used - registry)}"