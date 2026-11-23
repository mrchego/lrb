from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="is_cofounder",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Started the company together with the founder. Has the same "
                    "powers as the founder, but can be demoted by another founder "
                    "or co-founder. Never grants Django admin access."
                ),
            ),
        ),
    ]