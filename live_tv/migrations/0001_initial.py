from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="LiveTVChannel",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=180)),
                ("slug", models.SlugField(max_length=200, unique=True)),
                ("description", models.TextField(blank=True)),
                ("source_type", models.CharField(choices=[("youtube", "YouTube URL"), ("direct", "Direct Video Upload"), ("hls", "HLS / M3U8 Stream")], default="youtube", max_length=20)),
                ("youtube_url", models.URLField(blank=True, help_text="Paste YouTube watch, live, or embed URL.")),
                ("stream_url", models.URLField(blank=True, help_text="For HLS/M3U8 or external MP4/WebM URLs.")),
                ("video_file", models.FileField(blank=True, null=True, upload_to="live-tv/videos/%Y/%m/")),
                ("poster_image", models.ImageField(blank=True, null=True, upload_to="live-tv/posters/%Y/%m/")),
                ("channel_logo", models.ImageField(blank=True, null=True, upload_to="live-tv/logos/")),
                ("is_active", models.BooleanField(default=True)),
                ("is_live", models.BooleanField(default=True)),
                ("autoplay", models.BooleanField(default=False)),
                ("show_lower_third", models.BooleanField(default=True)),
                ("lower_third_label", models.CharField(default="BREAKING NEWS", max_length=60)),
                ("headline", models.CharField(default="The Up Media Live TV", max_length=180)),
                ("show_ticker", models.BooleanField(default=True)),
                ("ticker_label", models.CharField(default="TODAY'S NEWS", max_length=60)),
                ("ticker_text", models.CharField(default="Latest updates from The Up Media", max_length=260)),
                ("show_channel_logo", models.BooleanField(default=True)),
                ("meta_title", models.CharField(blank=True, max_length=160)),
                ("meta_description", models.CharField(blank=True, max_length=220)),
                ("display_order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["display_order", "title"],
            },
        ),
        migrations.AddIndex(
            model_name="livetvchannel",
            index=models.Index(fields=["is_active", "display_order"], name="live_tv_active_order_idx"),
        ),
        migrations.AddIndex(
            model_name="livetvchannel",
            index=models.Index(fields=["slug"], name="live_tv_slug_idx"),
        ),
    ]
