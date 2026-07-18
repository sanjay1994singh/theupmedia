from django.core.management.base import BaseCommand

from live_tv.hls import convert_live_channel_to_hls
from live_tv.models import LiveTVChannel


class Command(BaseCommand):
    help = "Convert uploaded Live TV channel videos to adaptive HLS."

    def add_arguments(self, parser):
        parser.add_argument("--id", type=int, dest="channel_id", help="Process one LiveTVChannel id.")
        parser.add_argument("--all", action="store_true", help="Process all direct uploaded Live TV channels.")
        parser.add_argument("--retry-failed", action="store_true", help="Include failed channels.")
        parser.add_argument("--retry-stale", action="store_true", help="Include processing jobs older than the stale cutoff.")

    def handle(self, *args, **options):
        queryset = LiveTVChannel.objects.filter(source_type=LiveTVChannel.SourceType.DIRECT, video_file__isnull=False).order_by("pk")
        if options.get("channel_id"):
            queryset = queryset.filter(pk=options["channel_id"])
        elif options.get("all"):
            statuses = [LiveTVChannel.HLSStatus.PENDING]
            if options.get("retry_failed"):
                statuses.append(LiveTVChannel.HLSStatus.FAILED)
            if options.get("retry_stale"):
                from datetime import timedelta
                from django.conf import settings
                from django.utils import timezone

                stale_cutoff = timezone.now() - timedelta(minutes=getattr(settings, "LIVE_TV_HLS_PROCESSING_STALE_MINUTES", 20))
                queryset = queryset.filter(
                    hls_status__in=statuses
                ) | LiveTVChannel.objects.filter(
                    source_type=LiveTVChannel.SourceType.DIRECT,
                    video_file__isnull=False,
                    hls_status=LiveTVChannel.HLSStatus.PROCESSING,
                    updated_at__lt=stale_cutoff,
                )
            else:
                queryset = queryset.filter(hls_status__in=statuses)
        else:
            self.stderr.write("Use --all, --retry-failed with --all, or --id <channel_id>.")
            return

        total = queryset.count()
        self.stdout.write(f"Processing {total} live TV channel video(s).")
        for channel in queryset:
            self.stdout.write(f"[{channel.pk}] {channel.title}")
            try:
                hls_path = convert_live_channel_to_hls(channel.pk)
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"[{channel.pk}] failed: {exc}"))
            else:
                self.stdout.write(self.style.SUCCESS(f"[{channel.pk}] completed: {hls_path}"))
