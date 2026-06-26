from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from news.models import Article


class Command(BaseCommand):
    help = "Check article slug/status/date and public URL response."

    def add_arguments(self, parser):
        parser.add_argument("article", help="Article id or slug")

    def handle(self, *args, **options):
        lookup = options["article"]
        queryset = Article.objects.select_related("category")
        if lookup.isdigit():
            article = queryset.get(pk=int(lookup))
        else:
            article = queryset.get(slug=lookup)

        url = f"{settings.SITE_DOMAIN}{article.get_absolute_url()}"
        self.stdout.write(f"ID: {article.pk}")
        self.stdout.write(f"Title: {article.title}")
        self.stdout.write(f"Slug: {article.slug}")
        self.stdout.write(f"Status: {article.status}")
        self.stdout.write(f"Published at: {article.published_at}")
        self.stdout.write(f"Now: {timezone.now()}")
        self.stdout.write(f"Public URL: {url}")
        self.stdout.write(f"Public manager can find it: {Article.published.filter(pk=article.pk).exists()}")

        request = Request(url, headers={"User-Agent": "facebookexternalhit/1.1"})
        try:
            with urlopen(request, timeout=20) as response:
                self.stdout.write(self.style.SUCCESS(f"HTTP: {response.status}"))
        except HTTPError as exc:
            self.stdout.write(self.style.ERROR(f"HTTP: {exc.code}"))
        except (URLError, TimeoutError, OSError) as exc:
            self.stdout.write(self.style.ERROR(f"HTTP check failed: {exc}"))
