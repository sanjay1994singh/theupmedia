from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("live_tv", "0007_socialrenderedvideo_render_format"),
    ]

    operations = [
        migrations.AlterField(
            model_name="socialrenderedvideo",
            name="render_format",
            field=models.CharField(default="16:9", db_default="16:9", max_length=10),
        ),
    ]
