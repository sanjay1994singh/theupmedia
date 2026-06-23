from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("live_tv", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="livetvchannel",
            name="slug",
            field=models.SlugField(blank=True, max_length=200, unique=True),
        ),
    ]
