from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("live_tv", "0002_alter_livetvchannel_slug"),
    ]

    operations = [
        migrations.CreateModel(
            name="MobileVideoUpload",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=180)),
                ("description", models.TextField(blank=True)),
                ("video", models.FileField(upload_to="mobile-video-uploads/%Y/%m/")),
                ("status", models.CharField(choices=[("pending", "Pending"), ("reviewed", "Reviewed"), ("published", "Published"), ("rejected", "Rejected")], default="pending", max_length=20)),
                ("uploaded_by_name", models.CharField(blank=True, max_length=120)),
                ("uploaded_by_phone", models.CharField(blank=True, max_length=30)),
                ("device_info", models.CharField(blank=True, max_length=220)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="mobilevideoupload",
            index=models.Index(fields=["status", "-created_at"], name="mobile_video_status_idx"),
        ),
    ]
