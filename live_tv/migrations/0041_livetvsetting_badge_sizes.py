from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("live_tv", "0040_persistent_ticker_clock"),
    ]

    operations = [
        migrations.AddField(
            model_name="livetvsetting",
            name="mobile_live_badge_size_percent",
            field=models.PositiveSmallIntegerField(
                default=100,
                help_text="Mobile app Live badge size in percent (40-200).",
                validators=[MinValueValidator(40), MaxValueValidator(200)],
            ),
        ),
        migrations.AddField(
            model_name="livetvsetting",
            name="web_live_badge_size_percent",
            field=models.PositiveSmallIntegerField(
                default=100,
                help_text="Web Live badge size in percent (40-200).",
                validators=[MinValueValidator(40), MaxValueValidator(200)],
            ),
        ),
    ]
