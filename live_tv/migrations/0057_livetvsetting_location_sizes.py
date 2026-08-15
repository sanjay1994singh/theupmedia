from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("live_tv", "0056_livetvsetting_channel_logo_sizes"),
    ]

    operations = [
        migrations.AddField(
            model_name="livetvsetting",
            name="mobile_live_location_size_percent",
            field=models.PositiveSmallIntegerField(
                default=100,
                help_text="Mobile app Live location badge size in percent (40-200).",
                validators=[MinValueValidator(40), MaxValueValidator(200)],
            ),
        ),
        migrations.AddField(
            model_name="livetvsetting",
            name="render_location_size_percent",
            field=models.PositiveSmallIntegerField(
                default=100,
                help_text="Rendered video location badge size in percent (40-200).",
                validators=[MinValueValidator(40), MaxValueValidator(200)],
            ),
        ),
        migrations.AddField(
            model_name="livetvsetting",
            name="web_live_location_size_percent",
            field=models.PositiveSmallIntegerField(
                default=100,
                help_text="Web Live location badge size in percent (40-200).",
                validators=[MinValueValidator(40), MaxValueValidator(200)],
            ),
        ),
    ]
