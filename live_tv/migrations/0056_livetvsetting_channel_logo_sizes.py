from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("live_tv", "0055_accountdeletionrequest"),
    ]

    operations = [
        migrations.AddField(
            model_name="livetvsetting",
            name="mobile_channel_logo_size_percent",
            field=models.PositiveSmallIntegerField(
                default=100,
                help_text="Mobile app channel logo size in percent (40-200).",
                validators=[MinValueValidator(40), MaxValueValidator(200)],
            ),
        ),
        migrations.AddField(
            model_name="livetvsetting",
            name="render_channel_logo_size_percent",
            field=models.PositiveSmallIntegerField(
                default=100,
                help_text="Rendered video channel logo size in percent (40-200).",
                validators=[MinValueValidator(40), MaxValueValidator(200)],
            ),
        ),
    ]
