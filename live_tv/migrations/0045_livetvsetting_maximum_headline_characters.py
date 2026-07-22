import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("live_tv", "0044_livetvchannel_reporter_fields")]
    operations = [
        migrations.AddField(
            model_name="livetvsetting",
            name="maximum_headline_characters",
            field=models.PositiveSmallIntegerField(
                default=100,
                help_text="Maximum characters shown in one headline part (30-200).",
                validators=[django.core.validators.MinValueValidator(30), django.core.validators.MaxValueValidator(200)],
            ),
        ),
    ]
