from django.db import migrations


def forwards(apps, schema_editor):
    """
    Runs once per schema (migrate_schemas): every company schema, and public.

    Company users:
    - Old non-founder owners become co-founders.
    - A company with no founder gets its oldest owner promoted to founder.
    - Every company user loses is_staff and is_superuser.

    Public-schema rows (company IS NULL) are untouched.
    """
    User = apps.get_model("accounts", "User")

    company_users = User.objects.filter(company__isnull=False)

    # 1. Convert old owners who aren't founders into co-founders.
    company_users.filter(
        is_superuser=True,
        is_founder=False,
    ).update(is_cofounder=True)

    # 2. Find companies that currently have co-founders.
    company_ids = (
        company_users.filter(is_cofounder=True)
        .values_list("company_id", flat=True)
        .distinct()
    )

    # 3. Make sure each company has a founder.
    for company_id in company_ids:
        has_founder = company_users.filter(
            company_id=company_id,
            is_founder=True,
        ).exists()

        if not has_founder:
            oldest = (
                company_users.filter(
                    company_id=company_id,
                    is_cofounder=True,
                )
                .order_by("created_at")
                .first()
            )

            if oldest is not None:
                oldest.is_cofounder = False
                oldest.is_founder = True

                oldest.save(
                    update_fields=[
                        "is_cofounder",
                        "is_founder",
                    ]
                )

    # 4. Company users must never have Django admin privileges.
    company_users.update(
        is_superuser=False,
        is_staff=False,
    )


def backwards(apps, schema_editor):
    """
    Best-effort reverse migration.

    Restore Django admin flags for founders and co-founders.
    """
    User = apps.get_model("accounts", "User")

    company_users = User.objects.filter(company__isnull=False)

    company_users.filter(is_founder=True).update(
        is_superuser=True,
        is_staff=True,
    )

    company_users.filter(is_cofounder=True).update(
        is_superuser=True,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_user_is_cofounder"),
    ]

    operations = [
        migrations.RunPython(
            forwards,
            backwards,
        ),
    ]