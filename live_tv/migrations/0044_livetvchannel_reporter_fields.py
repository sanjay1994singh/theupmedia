from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("live_tv", "0043_video_rotating_headlines")]
    operations = [
        migrations.AddField(model_name="livetvchannel", name="reporter_label", field=models.CharField(blank=True, default="REPORTER", max_length=60)),
        migrations.AddField(model_name="livetvchannel", name="reporter_name", field=models.CharField(blank=True, default="", max_length=120)),
    ]
