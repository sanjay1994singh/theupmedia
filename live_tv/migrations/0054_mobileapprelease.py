from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [("live_tv", "0053_blockeduser_shortscommentreport")]

    operations = [
        migrations.CreateModel(
            name="MobileAppRelease",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("channel", models.CharField(choices=[("testing", "Direct testing APK"), ("play_store", "Google Play Store")], default="testing", max_length=20)),
                ("version_name", models.CharField(help_text="Play Store version name, for example 1.0.1", max_length=30)),
                ("version_code", models.PositiveIntegerField(help_text="Must match Android versionCode in this release channel")),
                ("release_notes", models.TextField(blank=True)),
                ("testing_apk", models.FileField(blank=True, help_text="Testing channel only. Upload signed APK, not AAB.", null=True, upload_to="mobile-releases/testing/%Y/%m/")),
                ("play_store_url", models.URLField(default="https://play.google.com/store/apps/details?id=com.upmedia.livetv")),
                ("force_update", models.BooleanField(default=False, help_text="Show a non-cancelable update prompt for older app versions")),
                ("is_active", models.BooleanField(default=True)),
                ("published_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["-version_code", "-published_at"], "verbose_name": "Mobile App Release", "verbose_name_plural": "Mobile App Releases"},
        ),
        migrations.AddConstraint(model_name="mobileapprelease", constraint=models.UniqueConstraint(fields=("channel", "version_code"), name="unique_mobile_release_channel_version")),
    ]
