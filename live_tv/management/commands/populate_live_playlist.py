from pathlib import Path

from django.core.management.base import BaseCommand

from live_tv.hls import convert_live_channel_to_hls, probe_video
from live_tv.models import LiveTVChannel, LiveTVPlaylistItem
from live_tv.services import add_uploaded_video_to_live_playlist, get_main_live_channel


class Command(BaseCommand):
    help = "Populate the 24x7 main live playlist from eligible existing direct uploads."

    def handle(self, *args, **options):
        channel = get_main_live_channel(create=True)
        videos = LiveTVChannel.objects.filter(
            source_type=LiveTVChannel.SourceType.DIRECT,
            auto_add_to_live=True,
            auto_playlist_enabled=False,
            is_active=True,
        ).exclude(video_file="").order_by("created_at", "pk")
        added = skipped = failed = 0
        for video in videos:
            try:
                if not video.duration_seconds:
                    metadata = probe_video(Path(video.video_file.path))
                    video.duration = metadata.get("duration")
                    video.duration_seconds = max(0, int(round(metadata.get("duration") or 0)))
                    video.save(update_fields=["duration", "duration_seconds", "updated_at"])
                if video.hls_status != LiveTVChannel.HLSStatus.COMPLETED or not video.hls_master_url:
                    self.stdout.write(f"[{video.pk}] processing HLS: {video.title}")
                    convert_live_channel_to_hls(video.pk)
                    video.refresh_from_db()
                _item, created = add_uploaded_video_to_live_playlist(
                    video,
                    channel=channel,
                    priority=LiveTVPlaylistItem.Priority.NORMAL,
                )
                if created:
                    added += 1
                    self.stdout.write(self.style.SUCCESS(f"[{video.pk}] added: {video.title}"))
                else:
                    skipped += 1
                    self.stdout.write(f"[{video.pk}] duplicate skipped: {video.title}")
            except Exception as exc:
                failed += 1
                self.stderr.write(self.style.ERROR(f"[{video.pk}] failed: {exc}"))
        channel.refresh_from_db()
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. added={added}, skipped={skipped}, failed={failed}, "
                f"duration={channel.playlist_duration_seconds}s ({channel.playlist_duration_minutes:.2f} min)"
            )
        )
