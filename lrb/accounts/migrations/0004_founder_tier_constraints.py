from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_backfill_founder_tier"),
    ]

    operations = [
        # Company users cannot have Django admin privileges.
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(company__isnull=True)
                    | (
                        models.Q(is_staff=False)
                        & models.Q(is_superuser=False)
                    )
                ),
                name="user_staff_superuser_only_without_company",
            ),
        ),

        # A user cannot be both founder and co-founder.
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(
                condition=~models.Q(
                    is_founder=True,
                    is_cofounder=True,
                ),
                name="user_not_both_founder_and_cofounder",
            ),
        ),

        # Founder/co-founder roles are only allowed for company users.
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(company__isnull=False)
                    | (
                        models.Q(is_founder=False)
                        & models.Q(is_cofounder=False)
                    )
                ),
                name="user_founder_flags_require_company",
            ),
        ),
    ]