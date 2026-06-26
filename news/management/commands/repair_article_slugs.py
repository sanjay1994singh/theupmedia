from django.core.management.base import BaseCommand

from news.models import Article, ArticleSlugRedirect
from news.slug_utils import is_bad_article_slug, unique_article_slug


class Command(BaseCommand):
    help = "Regenerate blank or numeric article slugs and keep redirects from old slugs."

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", help="Regenerate every article slug.")
        parser.add_argument("--dry-run", action="store_true", help="Show changes without saving.")

    def handle(self, *args, **options):
        regenerate_all = options["all"]
        dry_run = options["dry_run"]
        updated = 0

        for article in Article.objects.all().order_by("pk"):
            old_slug = article.slug or ""
            if not regenerate_all and not is_bad_article_slug(old_slug):
                continue

            new_slug = unique_article_slug(Article, article.title, article.pk)
            if not new_slug or new_slug == old_slug:
                continue

            updated += 1
            self.stdout.write(f"{article.pk}: {old_slug or '(blank)'} -> {new_slug}")
            if dry_run:
                continue

            article.slug = new_slug
            article.save(update_fields=["slug", "updated_at"])
            if old_slug:
                ArticleSlugRedirect.objects.get_or_create(old_slug=old_slug, defaults={"article": article})

        prefix = "DRY RUN: " if dry_run else ""
        self.stdout.write(self.style.SUCCESS(f"{prefix}Article slugs repaired: {updated}"))
