from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("live_tv", "0004_mobileadmintoken"),
    ]

    operations = [
        migrations.CreateModel(
            name="SocialRenderedVideo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=180)),
                ("headline", models.CharField(blank=True, max_length=180)),
                ("ticker_text", models.CharField(blank=True, max_length=260)),
                ("lower_third_label", models.CharField(default="BREAKING NEWS", max_length=60)),
                ("original_video", models.FileField(upload_to="social-render/original/%Y/%m/")),
                ("rendered_video", models.FileField(blank=True, null=True, upload_to="social-render/rendered/%Y/%m/")),
                ("status", models.CharField(choices=[("processing", "Processing"), ("done", "Done"), ("failed", "Failed")], default="processing", max_length=20)),
                ("error_message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="social_rendered_videos", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
