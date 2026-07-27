import csv
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db.models import Count, Q

from news.content_quality import article_quality_warnings, article_word_count
from news.models import Article, Category


class Command(BaseCommand):
    help = "Audit published and draft articles for common AdSense/Search quality risks."

    def add_arguments(self, parser):
        parser.add_argument("--status", choices=["draft", "published"], help="Filter by article status.")
        parser.add_argument("--limit", type=int, default=200, help="Maximum number of articles to scan.")
        parser.add_argument("--csv", dest="csv_path", help="Optional CSV output path.")

    def handle(self, *args, **options):
        queryset = Article.objects.select_related("category", "state", "city", "author").order_by("-published_at")
        if options["status"]:
            queryset = queryset.filter(status=options["status"])

        articles = list(queryset[: options["limit"]])
        duplicate_titles = set(
            Article.objects.values("title")
            .annotate(total=Count("id"))
            .filter(total__gt=1)
            .values_list("title", flat=True)
        )
        empty_categories = list(
            Category.objects.filter(is_active=True)
            .annotate(published_count=Count("articles", filter=Q(articles__status=Article.Status.PUBLISHED)))
            .filter(published_count=0)
        )

        rows = []
        for article in articles:
            warnings = article_quality_warnings(article)
            if article.title in duplicate_titles:
                warnings.append("Duplicate title exists.")
            rows.append(
                {
                    "id": article.pk,
                    "status": article.status,
                    "title": article.title,
                    "category": article.category.name,
                    "word_count": article_word_count(article),
                    "warnings": " | ".join(warnings),
                    "url": article.get_absolute_url(),
                }
            )

        issues = [row for row in rows if row["warnings"]]
        self.stdout.write(f"Scanned articles: {len(rows)}")
        self.stdout.write(f"Articles with warnings: {len(issues)}")
        self.stdout.write(f"Active empty categories: {len(empty_categories)}")

        for row in issues[:50]:
            self.stdout.write(
                f"[{row['id']}] {row['title']} ({row['word_count']} words): {row['warnings']}"
            )

        if options["csv_path"]:
            output_path = Path(options["csv_path"])
            with output_path.open("w", newline="", encoding="utf-8") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=["id", "status", "title", "category", "word_count", "warnings", "url"])
                writer.writeheader()
                writer.writerows(rows)
            self.stdout.write(self.style.SUCCESS(f"CSV written: {output_path}"))
