from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("live_tv", "0038_hls_progress_percent"),
    ]

    operations = [
        migrations.AddField(
            model_name="livetvchannel",
            name="push_notification_sent_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.CreateModel(
            name="PushDevice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token", models.CharField(db_index=True, max_length=255, unique=True)),
                ("platform", models.CharField(blank=True, max_length=20)),
                ("device_name", models.CharField(blank=True, max_length=160)),
                ("is_active", models.BooleanField(default=True)),
                ("last_registered_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["-last_registered_at"]},
        ),
    ]
