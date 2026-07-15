from django.core.management.base import BaseCommand

from live_tv.models import SocialRenderedVideo
from live_tv.services import queue_broadcast_render_task


class Command(BaseCommand):
    help = "Queue pending, processing, or failed rendered video jobs."

    def add_arguments(self, parser):
        parser.add_argument("--failed", action="store_true", help="Queue failed jobs only.")
        parser.add_argument("--pending", action="store_true", help="Queue pending jobs only.")
        parser.add_argument("--processing", action="store_true", help="Queue processing jobs only.")
        parser.add_argument("--all-open", action="store_true", help="Queue pending, processing, and failed jobs.")
        parser.add_argument("--limit", type=int, default=50)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        statuses = []
        if options["all_open"] or not any([options["failed"], options["pending"], options["processing"]]):
            statuses = [
                SocialRenderedVideo.Status.PENDING,
                SocialRenderedVideo.Status.PROCESSING,
                SocialRenderedVideo.Status.FAILED,
            ]
        else:
            if options["failed"]:
                statuses.append(SocialRenderedVideo.Status.FAILED)
            if options["pending"]:
                statuses.append(SocialRenderedVideo.Status.PENDING)
            if options["processing"]:
                statuses.append(SocialRenderedVideo.Status.PROCESSING)

        limit = max(1, int(options["limit"]))
        queryset = (
            SocialRenderedVideo.objects.filter(status__in=statuses)
            .exclude(status__in=[SocialRenderedVideo.Status.COMPLETED, SocialRenderedVideo.Status.DONE])
            .order_by("created_at", "pk")[:limit]
        )
        jobs = list(queryset)
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING(f"Dry run: {len(jobs)} jobs would be queued."))
            for job in jobs:
                self.stdout.write(f"{job.pk}: {job.title} [{job.status}]")
            return

        queued = 0
        for job in jobs:
            job.status = SocialRenderedVideo.Status.PENDING
            job.progress_percent = 0
            job.error_message = ""
            job.retry_count += 1
            job.save(update_fields=["status", "progress_percent", "error_message", "retry_count", "updated_at"])
            queue_broadcast_render_task(job.pk)
            queued += 1

        self.stdout.write(self.style.SUCCESS(f"{queued} rendered video jobs queued."))
