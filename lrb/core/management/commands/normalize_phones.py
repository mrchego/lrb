"""Rewrite phone numbers that were stored before libphonenumber into E.164.

    docker compose -f docker-compose.local.yml run --rm django python manage.py normalize_phones
    docker compose -f docker-compose.local.yml run --rm django python manage.py normalize_phones --apply

Dry run by default: it only prints what it WOULD change. Numbers that are not valid are
reported and left exactly as they are - this command never deletes or blanks data.

Each company's numbers are read under that company's country (when it is an ISO code
like "KE"), else PHONE_DEFAULT_REGION. A number that already starts with "+" never
depends on that guess.
"""
from __future__ import annotations

from collections import Counter

from django.core.management.base import BaseCommand
from django.db import transaction
from django_tenants.utils import tenant_context

from lrb.accounts.models import User
from lrb.company.models.company import Company
from lrb.core.phone import CONTACT, inspect_phone, resolve_region


class Command(BaseCommand):
    help = "Rewrite stored company and user phone numbers as E.164 (dry run unless --apply)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Save the changes. Without it, nothing is written.",
        )

    def handle(self, *args, apply: bool = False, **options):
        stats: Counter = Counter()
        for company in Company.objects.order_by("slug"):
            region = resolve_region(company.country)
            self._fix(company, f"company {company.slug}", region, apply, stats, "companies")

            if company.schema_name == "public":
                continue  # the platform tenant: it has a company row, but no tenant user tables
            with tenant_context(company), transaction.atomic():
                # _base_manager: include every row, whatever the default manager hides.
                for user in User._base_manager.exclude(phone=""):
                    self._fix(user, f"{company.slug}: {user.email}", region, apply, stats, "users")

        verb = "fixed" if apply else "would fix"
        self.stdout.write("")
        for kind in ("companies", "users"):
            self.stdout.write(
                f"{kind}: {stats[f'{kind}_changed']} {verb}, "
                f"{stats[f'{kind}_ok']} already E.164, "
                f"{stats[f'{kind}_invalid']} invalid (left untouched)"
            )
        if not apply and sum(v for k, v in stats.items() if k.endswith("_changed")):
            self.stdout.write(self.style.NOTICE("Dry run. Re-run with --apply to save."))

    def _fix(self, obj, label: str, region: str, apply: bool, stats: Counter, kind: str):
        old = obj.phone
        if not old:
            return
        result = inspect_phone(value=old, region=region, policy=CONTACT)
        if not result.ok:
            stats[f"{kind}_invalid"] += 1
            self.stdout.write(self.style.WARNING(f"INVALID    {label}: {old!r} - {result.message}"))
            return
        new = result.info.e164
        if new == old:
            stats[f"{kind}_ok"] += 1
            return
        stats[f"{kind}_changed"] += 1
        self.stdout.write(f"{'FIXED' if apply else 'WOULD FIX':<10} {label}: {old!r} -> {new}")
        if apply:
            obj.phone = new
            # save() rather than queryset.update(): the cache layer invalidates on
            # model save signals, and update() would leave stale cached rows behind.
            obj.save(update_fields=["phone"])
