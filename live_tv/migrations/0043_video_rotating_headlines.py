import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


def seed_existing_headlines(apps, schema_editor):
    LiveTVChannel = apps.get_model("live_tv", "LiveTVChannel")
    LiveTVVideoHeadline = apps.get_model("live_tv", "LiveTVVideoHeadline")
    for video in LiveTVChannel.objects.exclude(headline="").iterator():
        text = (video.headline or "").strip()
        if text:
            LiveTVVideoHeadline.objects.get_or_create(
                video_id=video.pk,
                position=0,
                defaults={"text": text, "is_active": True},
            )


class Migration(migrations.Migration):

    dependencies = [
        ("live_tv", "0042_collapse_duplicate_source_renders"),
    ]

    operations = [
        migrations.AddField(
            model_name="livetvchannel",
            name="headline_change_seconds",
            field=models.PositiveSmallIntegerField(
                default=2,
                help_text="Seconds before the next headline appears.",
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(60),
                ],
            ),
        ),
        migrations.AddField(
            model_name="livetvchannel",
            name="repeat_headlines",
            field=models.BooleanField(
                default=True,
                help_text="Repeat this video's headline sequence until the video ends.",
            ),
        ),
        migrations.CreateModel(
            name="LiveTVVideoHeadline",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("text", models.CharField(max_length=240)),
                ("position", models.PositiveSmallIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "video",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="rotating_headlines",
                        to="live_tv.livetvchannel",
                    ),
                ),
            ],
            options={"ordering": ["position", "pk"]},
        ),
        migrations.RunPython(seed_existing_headlines, migrations.RunPython.noop),
    ]
