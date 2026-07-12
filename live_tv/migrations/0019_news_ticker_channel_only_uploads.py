from django.db import migrations, models
from django.utils.text import slugify


def unique_channel_slug(LiveTVChannel, title, upload_id):
    base_slug = slugify(title)[:180] or f"mobile-video-{upload_id}"
    slug = base_slug
    counter = 2
    while LiveTVChannel.objects.filter(slug=slug).exists():
        suffix = f"-{counter}"
        slug = f"{base_slug[:200 - len(suffix)]}{suffix}"
        counter += 1
    return slug


def seed_ticker_and_move_mobile_uploads(apps, schema_editor):
    LiveTVSetting = apps.get_model("live_tv", "LiveTVSetting")
    NewsTickerSetting = apps.get_model("live_tv", "NewsTickerSetting")
    LiveTVChannel = apps.get_model("live_tv", "LiveTVChannel")
    MobileVideoUpload = apps.get_model("live_tv", "MobileVideoUpload")

    setting = LiveTVSetting.objects.filter(pk=1).first()
    NewsTickerSetting.objects.update_or_create(
        pk=1,
        defaults={
            "label": getattr(setting, "default_ticker_label", "ताज़ा खबर") if setting else "ताज़ा खबर",
            "text": getattr(setting, "default_ticker_text", "Latest updates from The Up Media") if setting else "Latest updates from The Up Media",
            "speed_seconds": getattr(setting, "ticker_speed_seconds", 22) if setting else 22,
            "mobile_speed_seconds": getattr(setting, "mobile_ticker_speed_seconds", 12) if setting else 12,
            "style": "red_white_slant",
        },
    )

    base_order = LiveTVChannel.objects.count()
    lower_label = getattr(setting, "default_lower_third_label", "BREAKING NEWS") if setting else "BREAKING NEWS"
    default_headline = getattr(setting, "default_headline", "The Up Media Live TV") if setting else "The Up Media Live TV"

    for index, upload in enumerate(MobileVideoUpload.objects.all().order_by("created_at"), start=1):
        if not upload.video:
            continue
        title = upload.title or "The Up Media Live TV"
        LiveTVChannel.objects.create(
            title=title[:180],
            slug=unique_channel_slug(LiveTVChannel, title, upload.pk),
            description=getattr(upload, "description", "") or "",
            source_type="direct",
            video_file=upload.video.name,
            is_active=True,
            is_live=True,
            lower_third_label=lower_label,
            headline=title[:180] or default_headline,
            ticker_label=getattr(setting, "default_ticker_label", "TODAY'S NEWS") if setting else "TODAY'S NEWS",
            ticker_text="",
            display_order=base_order + index,
            meta_title=title[:160],
            meta_description=(getattr(upload, "description", "") or title)[:220],
        )


class Migration(migrations.Migration):

    dependencies = [
        ("live_tv", "0018_socialrenderedvideo_frame_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="NewsTickerSetting",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("label", models.CharField(default="ताज़ा खबर", max_length=60)),
                ("text", models.TextField(default="Latest updates from The Up Media")),
                ("speed_seconds", models.PositiveSmallIntegerField(default=22)),
                ("mobile_speed_seconds", models.PositiveSmallIntegerField(default=12)),
                ("style", models.CharField(default="red_white_slant", max_length=60)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "News Ticker Setting",
                "verbose_name_plural": "News Ticker Settings",
            },
        ),
        migrations.RunPython(seed_ticker_and_move_mobile_uploads, migrations.RunPython.noop),
        migrations.DeleteModel(
            name="MobileVideoUpload",
        ),
    ]
