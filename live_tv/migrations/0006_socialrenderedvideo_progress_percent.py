from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("live_tv", "0005_socialrenderedvideo"),
    ]

    operations = [
        migrations.AddField(
            model_name="socialrenderedvideo",
            name="progress_percent",
            field=models.PositiveSmallIntegerField(default=0),
        ),
    ]
