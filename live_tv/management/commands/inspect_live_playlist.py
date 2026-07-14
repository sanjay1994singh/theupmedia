from django.core.management.base import BaseCommand

from live_tv.services import calculate_current_playback, get_main_live_channel


class Command(BaseCommand):
    help = "Inspect the main auto live playlist and synchronized playback state."

    def handle(self, *args, **options):
        channel = get_main_live_channel(create=False)
        if not channel:
            self.stderr.write(self.style.ERROR("Main auto live playlist channel is not configured."))
            return
        items = channel.playlist_items.filter(is_active=True).select_related("video").order_by("position", "pk")
        self.stdout.write(f"Channel: [{channel.pk}] {channel.title} ({channel.slug})")
        self.stdout.write(
            f"Items: {items.count()} | duration: {channel.playlist_duration_seconds}s | "
            f"target: {channel.target_playlist_duration_seconds}s | version: {channel.playlist_version}"
        )
        for item in items:
            self.stdout.write(
                f"  {item.position + 1:02d}. [{item.video_id}] {item.video.title} - "
                f"{item.duration_seconds}s - {item.video.hls_status}"
            )
        state = calculate_current_playback(channel)
        if not state:
            self.stdout.write("Current: playlist is empty or playback is unavailable.")
            return
        next_title = state["next_entry"].video.title if state.get("next_entry") else "-"
        self.stdout.write(
            self.style.SUCCESS(
                f"Current: [{state['video'].pk}] {state['video'].title} at {state['seek_position']:.2f}s; "
                f"next: {next_title}; active cycle v{state['playlist_version']}"
            )
        )
