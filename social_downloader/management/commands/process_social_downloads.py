import time

from django.core.management.base import BaseCommand

from social_downloader.models import SocialMediaDownload
from social_downloader.services.downloader import run_download_job


class Command(BaseCommand):
    help = "Process pending Social Video Downloader jobs."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Process pending jobs once and exit.")
        parser.add_argument("--sleep", type=int, default=5, help="Seconds to wait between polling loops.")
        parser.add_argument("--limit", type=int, default=1, help="Jobs to process per loop.")

    def handle(self, *args, **options):
        while True:
            jobs = list(
                SocialMediaDownload.objects.filter(status=SocialMediaDownload.Status.PENDING)
                .order_by("created_at")
                .values_list("pk", flat=True)[: options["limit"]]
            )
            if not jobs and options["once"]:
                self.stdout.write("No pending jobs.")
                return
            for job_id in jobs:
                self.stdout.write(f"Processing social download job {job_id}")
                run_download_job(job_id)
            if options["once"]:
                return
            time.sleep(options["sleep"])

