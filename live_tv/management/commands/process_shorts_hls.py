from django.core.management.base import BaseCommand

from live_tv.hls import convert_short_to_hls
from live_tv.models import ShortsVideo


class Command(BaseCommand):
    help = "Convert Shorts videos to adaptive HLS."

    def add_arguments(self, parser):
        parser.add_argument("--id", type=int, dest="short_id", help="Process one ShortsVideo id.")
        parser.add_argument("--all", action="store_true", help="Process every published shorts video.")
        parser.add_argument("--retry-failed", action="store_true", help="Include failed videos.")

    def handle(self, *args, **options):
        queryset = ShortsVideo.objects.filter(is_published=True).order_by("pk")
        if options.get("short_id"):
            queryset = queryset.filter(pk=options["short_id"])
        elif options.get("all"):
            pass
        else:
            statuses = [ShortsVideo.HLSStatus.PENDING]
            if options.get("retry_failed"):
                statuses.append(ShortsVideo.HLSStatus.FAILED)
            queryset = queryset.filter(hls_status__in=statuses)

        total = queryset.count()
        self.stdout.write(f"Processing {total} shorts video(s).")
        for short in queryset:
            self.stdout.write(f"[{short.pk}] {short.title or short.video_file.name}")
            try:
                hls_path = convert_short_to_hls(short.pk)
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f"[{short.pk}] failed: {exc}"))
            else:
                self.stdout.write(self.style.SUCCESS(f"[{short.pk}] completed: {hls_path}"))
