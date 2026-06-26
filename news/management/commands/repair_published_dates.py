from django.core.management.base import BaseCommand
from django.utils import timezone

from news.models import Article


class Command(BaseCommand):
    help = "Set future published_at values to now for already-published articles."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show affected rows without saving.")

    def handle(self, *args, **options):
        now = timezone.now()
        queryset = Article.objects.filter(status=Article.Status.PUBLISHED, published_at__gt=now)
        count = queryset.count()
        for article in queryset.order_by("published_at")[:50]:
            self.stdout.write(f"{article.pk}: {article.published_at} -> {now} | {article.slug}")
        if not options["dry_run"]:
            queryset.update(published_at=now)
        prefix = "DRY RUN: " if options["dry_run"] else ""
        self.stdout.write(self.style.SUCCESS(f"{prefix}Published dates repaired: {count}"))
