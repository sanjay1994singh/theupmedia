from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("live_tv", "0006_socialrenderedvideo_progress_percent"),
    ]

    operations = [
        migrations.AddField(
            model_name="socialrenderedvideo",
            name="render_format",
            field=models.CharField(default="16:9", max_length=10),
        ),
    ]
