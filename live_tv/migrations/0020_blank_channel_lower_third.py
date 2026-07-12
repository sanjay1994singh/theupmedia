from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("live_tv", "0019_news_ticker_channel_only_uploads"),
    ]

    operations = [
        migrations.AlterField(
            model_name="livetvchannel",
            name="headline",
            field=models.CharField(blank=True, default="", max_length=180),
        ),
        migrations.AlterField(
            model_name="livetvchannel",
            name="lower_third_label",
            field=models.CharField(blank=True, default="", max_length=60),
        ),
    ]
