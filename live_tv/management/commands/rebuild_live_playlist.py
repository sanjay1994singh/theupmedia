from django.core.management.base import BaseCommand

from live_tv.models import LiveTVChannel
from live_tv.services import get_main_live_channel, rebuild_live_playlist


class Command(BaseCommand):
    help = "Rebuild the canonical 24x7 playlist from all currently eligible processed uploads."

    def handle(self, *args, **options):
        channel = get_main_live_channel(create=True)
        videos = LiveTVChannel.objects.filter(
            source_type=LiveTVChannel.SourceType.DIRECT,
            auto_add_to_live=True,
            auto_playlist_enabled=False,
            is_active=True,
            duration_seconds__gt=0,
        ).exclude(video_file="").order_by("created_at", "pk")
        channel = rebuild_live_playlist(videos, channel=channel)
        self.stdout.write(
            self.style.SUCCESS(
                f"Playlist rebuilt: {channel.playlist_items.filter(is_active=True).count()} items, "
                f"{channel.playlist_duration_seconds}s, version {channel.playlist_version}."
            )
        )
