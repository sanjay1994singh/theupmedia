import math

import django.db.models.deletion
from django.db import migrations, models


def backfill_durations_and_main_channel(apps, schema_editor):
    LiveTVChannel = apps.get_model("live_tv", "LiveTVChannel")
    for channel in LiveTVChannel.objects.all().iterator():
        try:
            seconds = max(0, int(math.floor(float(channel.duration or 0))))
        except (TypeError, ValueError, OverflowError):
            seconds = 0
        if channel.duration_seconds != seconds:
            LiveTVChannel.objects.filter(pk=channel.pk).update(duration_seconds=seconds)

    if not LiveTVChannel.objects.filter(source_type="playlist", auto_playlist_enabled=True).exists():
        slug = "the-up-media-live-auto"
        counter = 2
        while LiveTVChannel.objects.filter(slug=slug).exists():
            slug = f"the-up-media-live-auto-{counter}"
            counter += 1
        LiveTVChannel.objects.create(
            title="The Up Media Live",
            slug=slug,
            source_type="playlist",
            auto_playlist_enabled=True,
            auto_add_to_live=False,
            is_active=True,
            is_live=True,
            loop_enabled=True,
            target_playlist_duration_seconds=10800,
            display_order=0,
        )


class Migration(migrations.Migration):
    dependencies = [("live_tv", "0031_shortsvideo_views_count_channelfollow_shortslike")]

    operations = [
        migrations.AddField(
            model_name="livetvchannel",
            name="auto_add_to_live",
            field=models.BooleanField(
                default=True,
                help_text="Automatically add this uploaded video to the main live playlist.",
            ),
        ),
        migrations.AddField(
            model_name="livetvchannel",
            name="auto_playlist_enabled",
            field=models.BooleanField(
                default=False,
                help_text="Use this record as the main synchronized auto live channel.",
            ),
        ),
        migrations.AddField(
            model_name="livetvchannel",
            name="duration_seconds",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="livetvchannel",
            name="last_playlist_update",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="livetvchannel",
            name="loop_enabled",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="livetvchannel",
            name="playback_started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="livetvchannel",
            name="playlist_version",
            field=models.PositiveBigIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="livetvchannel",
            name="target_playlist_duration_seconds",
            field=models.PositiveIntegerField(
                default=10800,
                help_text="Target live playlist duration. 10800 seconds = 3 hours.",
            ),
        ),
        migrations.AlterField(
            model_name="livetvchannel",
            name="source_type",
            field=models.CharField(
                choices=[
                    ("youtube", "YouTube URL"),
                    ("direct", "Direct Video Upload"),
                    ("hls", "HLS / M3U8 Stream"),
                    ("playlist", "Auto Live Playlist"),
                ],
                default="youtube",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="LiveTVPlaylistItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("position", models.PositiveIntegerField(default=0)),
                ("duration_seconds", models.PositiveIntegerField(default=0)),
                (
                    "priority",
                    models.CharField(
                        choices=[("normal", "Add to End"), ("next", "Play Next"), ("immediate", "Play Immediately")],
                        default="normal",
                        max_length=20,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("added_at", models.DateTimeField(auto_now_add=True)),
                ("removed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "channel",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="playlist_items", to="live_tv.livetvchannel"),
                ),
                (
                    "video",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="included_in_playlists", to="live_tv.livetvchannel"),
                ),
            ],
            options={
                "ordering": ["position", "pk"],
                "indexes": [models.Index(fields=["channel", "is_active", "position"], name="live_playlist_order_idx")],
                "constraints": [
                    models.UniqueConstraint(fields=("channel", "video"), name="unique_live_playlist_video"),
                    models.CheckConstraint(condition=~models.Q(channel=models.F("video")), name="live_playlist_no_self_ref"),
                ],
            },
        ),
        migrations.CreateModel(
            name="LiveTVPlaylistCycle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("version", models.PositiveBigIntegerField()),
                ("starts_at", models.DateTimeField()),
                ("total_duration_seconds", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "channel",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="playlist_cycles", to="live_tv.livetvchannel"),
                ),
            ],
            options={
                "ordering": ["-starts_at", "-version"],
                "indexes": [models.Index(fields=["channel", "starts_at"], name="live_cycle_start_idx")],
                "constraints": [models.UniqueConstraint(fields=("channel", "version"), name="unique_live_playlist_cycle_version")],
            },
        ),
        migrations.CreateModel(
            name="LiveTVPlaylistCycleItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("position", models.PositiveIntegerField(default=0)),
                ("duration_seconds", models.PositiveIntegerField(default=0)),
                (
                    "cycle",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="live_tv.livetvplaylistcycle"),
                ),
                (
                    "playlist_item",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="cycle_items", to="live_tv.livetvplaylistitem"),
                ),
                (
                    "video",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="playlist_cycle_entries", to="live_tv.livetvchannel"),
                ),
            ],
            options={
                "ordering": ["position", "pk"],
                "indexes": [models.Index(fields=["cycle", "position"], name="live_cycle_item_order_idx")],
                "constraints": [models.UniqueConstraint(fields=("cycle", "position"), name="unique_live_cycle_position")],
            },
        ),
        migrations.RunPython(backfill_durations_and_main_channel, migrations.RunPython.noop),
    ]
