from django.core.management.base import BaseCommand

from news.article_defaults import get_default_author, get_or_make_category, get_or_make_location, infer_taxonomy
from news.models import Article
from news.thumbnail_utils import attach_text_thumbnail


class Command(BaseCommand):
    help = "Apply default author, related taxonomy and clean text thumbnails to existing articles."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Save changes. Without this, preview only.")
        parser.add_argument("--all", action="store_true", help="Update all articles, not only drafts/generated rows.")
        parser.add_argument("--force-author", action="store_true", help="Replace existing author with the default author.")
        parser.add_argument("--force-taxonomy", action="store_true", help="Replace existing category/state/city when inferred.")
        parser.add_argument("--regenerate-thumbnails", action="store_true", help="Create fresh simple title thumbnails.")
        parser.add_argument("--limit", type=int, default=500)

    def handle(self, *args, **options):
        author = get_default_author()
        queryset = Article.objects.all().order_by("id")
        if not options["all"]:
            queryset = queryset.filter(status=Article.Status.DRAFT)
        queryset = queryset[: options["limit"]]

        updated = 0
        thumbed = 0
        self.stdout.write(f"Default author: {author or 'not found'}")

        for article in queryset:
            changed = False
            category_name, state_name, city_name = infer_taxonomy(article.title)

            if author and (options["force_author"] or not article.author_id):
                article.author = author
                article.reviewed_by = article.reviewed_by or author
                article.fact_checked_by = article.fact_checked_by or author
                changed = True

            if category_name and (options["force_taxonomy"] or not article.category_id):
                category = get_or_make_category(category_name)
                if category and article.category_id != category.id:
                    article.category = category
                    changed = True

            if state_name and (options["force_taxonomy"] or not article.state_id or not article.city_id):
                state, city = get_or_make_location(state_name, city_name)
                if state and (options["force_taxonomy"] or not article.state_id):
                    article.state = state
                    changed = True
                if city and (options["force_taxonomy"] or not article.city_id):
                    article.city = city
                    changed = True

            if not article.image_alt_text:
                article.image_alt_text = article.title[:180]
                changed = True
            if not article.image_caption:
                article.image_caption = f"{article.title[:120]} - The Up Media illustration"
                changed = True
            if not article.image_credit:
                article.image_credit = "The Up Media"
                changed = True

            self.stdout.write(
                f"{article.pk}: {article.title[:70]} | "
                f"author={article.author or '-'} | "
                f"category={article.category.name if article.category_id else '-'} | "
                f"state={article.state.name if article.state_id else '-'} | "
                f"city={article.city.name if article.city_id else '-'}"
            )

            if not options["apply"]:
                continue

            if changed:
                article.save()
                updated += 1

            if options["regenerate_thumbnails"]:
                prefix = "irfan" if "irfan" in str(article.title).lower() else "queue"
                attach_text_thumbnail(article, folder="generated", prefix=prefix)
                thumbed += 1

        self.stdout.write(self.style.SUCCESS(f"Updated: {updated}, thumbnails: {thumbed}"))
