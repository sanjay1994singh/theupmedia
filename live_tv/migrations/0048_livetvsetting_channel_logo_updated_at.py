from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("live_tv", "0047_livetvsetting_splash_screen_seconds"),
    ]

    operations = [
        migrations.AddField(
            model_name="livetvsetting",
            name="channel_logo_updated_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
    ]
