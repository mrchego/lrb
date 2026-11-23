"""Founder / co-founder tier. Uses the existing `w` World fixture.

In the World fixture change:
    self.owner_a = self.new_user(self.a, is_founder=True)
    self.owner_b = self.new_user(self.b, is_founder=True)
and add:
    self.cofounder_a = self.new_user(self.a, is_cofounder=True)
"""
import pytest
from django.db import IntegrityError, transaction

from lrb.accounts.models import User
from lrb.accounts.services.demote_cofounder import demote_cofounder
from lrb.accounts.services.promote_to_cofounder import promote_to_cofounder
from lrb.core.exceptions import ApplicationError, ErrorCode
from django_tenants.utils import tenant_context

@pytest.fixture
def in_a(w):
    with tenant_context(w.a):
        yield

@pytest.fixture
def cofounder_a(w, in_a):
    return w.new_user(w.a, is_cofounder=True)

def _cid(w):
    return str(w.a.id)


def test_create_user_cannot_set_staff_or_superuser(w):
    with pytest.raises(TypeError):
        w.new_user(w.a, is_superuser=True)
    with pytest.raises(TypeError):
        w.new_user(w.a, is_staff=True)


@pytest.mark.parametrize("flag", ["is_staff", "is_superuser"])
def test_database_refuses_staff_or_superuser_on_company_user(w, in_a, flag):
    u = w.new_user(w.a)
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.filter(pk=u.pk).update(**{flag: True})


def test_model_clean_refuses_company_superuser(w):
    from django.core.exceptions import ValidationError

    u = w.new_user(w.a)
    u.is_superuser = True
    with pytest.raises(ValidationError):
        u.full_clean()


def test_promote_gives_cofounder_only(w, in_a):
    u = w.new_user(w.a)
    promote_to_cofounder(user_id=u.id, company_id=_cid(w))
    u.refresh_from_db()
    assert u.is_cofounder and u.has_founder_access
    assert not u.is_founder and not u.is_superuser and not u.is_staff


def test_cannot_promote_inactive_or_invited_user(w, in_a):
    u = w.new_user(w.a, can_login=False, is_active=False)
    with pytest.raises(ApplicationError , match="active"):
        promote_to_cofounder(user_id=u.id, company_id=_cid(w))


def test_cannot_promote_twice(w, in_a, cofounder_a):
    with pytest.raises(ApplicationError):
        promote_to_cofounder(user_id=cofounder_a.id, company_id=_cid(w))


def test_demote_cofounder(w, in_a, cofounder_a):
    demote_cofounder(user_id=cofounder_a.id, company_id=_cid(w))
    cofounder_a.refresh_from_db()
    assert not cofounder_a.has_founder_access


def test_founder_cannot_be_demoted_even_by_a_cofounder(w, in_a):
    with pytest.raises(ApplicationError) as e:
        demote_cofounder(user_id=w.owner_a.id, company_id=_cid(w))
    assert e.value.code == ErrorCode.CANNOT_MODIFY_FOUNDER


def test_cofounder_can_run_founder_only_mutations(w, cofounder_a):
    r = w.run(
        cofounder_a,
        f'mutation {{ lockUser(input: {{userId: "{w.staff_a.id}", durationMinutes: 5}}) '
        f"{{ success }} }}",
    )
    assert not r.errors and r.data["lockUser"]["success"] is True


def test_plain_staff_cannot_promote(w):
    r = w.run(
        w.staff_a,
        f'mutation {{ promoteToCofounder(input: {{userId: "{w.staff_a.id}"}}) '
        f"{{ success }} }}",
    )
    assert r.errors  # permission denied


def test_graphql_no_longer_exposes_staff_or_superuser(w):
    r = w.run(w.owner_a, "{ me { isSuperuser } }")
    assert r.errors
    r = w.run(w.owner_a, "{ me { isStaff } }")
    assert r.errors
    r = w.run(w.owner_a, "{ me { isFounder isCofounder hasFounderAccess } }")
    assert not r.errors and r.data["me"]["hasFounderAccess"] is True


def test_createsuperuser_rejects_company(w):
    with pytest.raises(ValueError):
        User.objects.create_superuser(
            email="dev@example.test", password="Str0ng-Passw0rd!", company=w.a
        )