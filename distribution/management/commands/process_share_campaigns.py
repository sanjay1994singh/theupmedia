from django.core.management.base import BaseCommand

from distribution.models import ShareCampaign
from distribution.services import run_campaign


class Command(BaseCommand):
    help = "Process queued share campaigns. Use from cron if you do not want to run campaigns from the browser."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=5)

    def handle(self, *args, **options):
        limit = max(1, min(options["limit"], 20))
        campaigns = ShareCampaign.objects.filter(status=ShareCampaign.Status.QUEUED).order_by("created_at")[:limit]
        processed = 0
        for campaign in campaigns:
            run_campaign(campaign)
            processed += 1
        self.stdout.write(self.style.SUCCESS(f"Processed campaigns: {processed}"))
