import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from social_downloader.models import SocialMediaDownload
from social_downloader.services.paths import resolve_download_path


class Command(BaseCommand):
    help = "Expire and delete old Social Video Downloader files."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        cutoff = timezone.now() - timezone.timedelta(days=options["days"])
        jobs = SocialMediaDownload.objects.filter(
            status=SocialMediaDownload.Status.COMPLETED,
            completed_at__lt=cutoff,
        ).exclude(relative_file_path="")
        count = 0
        media_root = Path(settings.MEDIA_ROOT).resolve()
        for job in jobs:
            try:
                path = resolve_download_path(job.relative_file_path)
            except ValueError:
                self.stderr.write(f"Skipping unsafe path for job {job.pk}")
                continue
            self.stdout.write(f"{'Would delete' if options['dry_run'] else 'Deleting'} {path}")
            if not options["dry_run"]:
                path.unlink(missing_ok=True)
                parent = path.parent
                if media_root in parent.resolve().parents:
                    shutil.rmtree(parent, ignore_errors=True)
                job.status = SocialMediaDownload.Status.EXPIRED
                job.relative_file_path = ""
                job.save(update_fields=["status", "relative_file_path", "updated_at"])
            count += 1
        self.stdout.write(f"{count} job(s) {'matched' if options['dry_run'] else 'cleaned'}.")
