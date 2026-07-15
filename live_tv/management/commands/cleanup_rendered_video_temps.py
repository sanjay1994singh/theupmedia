import shutil
import tempfile
from datetime import timedelta
from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils import timezone

from live_tv.models import SocialRenderedVideo


class Command(BaseCommand):
    help = "Remove stale live render temp folders and mark very old processing renders as failed."

    def add_arguments(self, parser):
        parser.add_argument("--hours", type=int, default=24)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        hours = max(int(options["hours"]), 1)
        dry_run = options["dry_run"]
        cutoff = timezone.now() - timedelta(hours=hours)
        marked = 0

        stale_jobs = SocialRenderedVideo.objects.filter(
            status__in=[SocialRenderedVideo.Status.PENDING, SocialRenderedVideo.Status.PROCESSING],
            updated_at__lt=cutoff,
        )
        if not dry_run:
            marked = stale_jobs.update(
                status=SocialRenderedVideo.Status.FAILED,
                progress_percent=0,
                error_message="Render timeout cleanup: job was stale.",
            )
        else:
            marked = stale_jobs.count()

        removed = 0
        temp_root = Path(tempfile.gettempdir())
        for folder in temp_root.glob("live-render-*"):
            try:
                if not folder.is_dir():
                    continue
                mtime = timezone.datetime.fromtimestamp(folder.stat().st_mtime, tz=timezone.get_current_timezone())
                if mtime >= cutoff:
                    continue
                if not dry_run:
                    shutil.rmtree(folder, ignore_errors=True)
                removed += 1
            except OSError:
                self.stderr.write(f"Could not inspect temp folder: {folder}")

        self.stdout.write(self.style.SUCCESS(f"Cleanup complete. stale_jobs={marked}, temp_dirs={removed}, dry_run={dry_run}"))
