from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("live_tv", "0017_facebooklivesetting_log_file"),
    ]

    operations = [
        migrations.AddField(
            model_name="socialrenderedvideo",
            name="ticker_label",
            field=models.CharField(default="BREAKING NEWS", max_length=60),
        ),
        migrations.AddField(
            model_name="socialrenderedvideo",
            name="frame_category",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="socialrenderedvideo",
            name="frame_template",
            field=models.CharField(blank=True, max_length=60),
        ),
    ]
