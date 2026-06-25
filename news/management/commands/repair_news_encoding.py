import json

from django.core.management.base import BaseCommand

from news.models import Article, FetchedNews
from news.services.ai_writer import build_hindi_news_draft, clean_text, has_mojibake, repair_mojibake


class Command(BaseCommand):
    help = "Repair mojibake Hindi text in imported news and linked articles."

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", help="Regenerate all imported news, not only bad-looking rows.")
        parser.add_argument("--articles-only", action="store_true", help="Repair only Article text fields.")
        parser.add_argument("--imports-only", action="store_true", help="Repair only FetchedNews rows and linked articles.")
        parser.add_argument("--dry-run", action="store_true", help="Show counts without saving changes.")

    def handle(self, *args, **options):
        include_all = options["all"]
        dry_run = options["dry_run"]
        repair_articles = not options["imports_only"]
        repair_imports = not options["articles_only"]

        imported_count = 0
        article_count = 0

        if repair_imports:
            for fetched_news in FetchedNews.objects.select_related("source", "created_article"):
                values = [
                    fetched_news.original_title,
                    fetched_news.original_summary,
                    fetched_news.ai_title,
                    fetched_news.ai_summary,
                    fetched_news.ai_content,
                ]
                if not include_all and not any(has_mojibake(value) for value in values):
                    continue

                original_title = clean_text(fetched_news.original_title)
                original_summary = clean_text(fetched_news.original_summary)
                draft = build_hindi_news_draft(
                    original_title=original_title,
                    original_summary=original_summary,
                    source_name=fetched_news.source.name,
                    source_url=fetched_news.original_url,
                )
                if not dry_run:
                    fetched_news.original_title = original_title[:300]
                    fetched_news.original_summary = original_summary
                    fetched_news.ai_title = draft.ai_title
                    fetched_news.ai_summary = draft.ai_summary
                    fetched_news.ai_content = draft.ai_content
                    fetched_news.ai_slug = draft.slug
                    fetched_news.source_credit = draft.source_credit
                    fetched_news.source_url = draft.source_url
                    fetched_news.fact_points = json.dumps(draft.fact_points, ensure_ascii=False)
                    fetched_news.seo_keywords = draft.seo_keywords
                    fetched_news.internal_note = draft.internal_note
                    fetched_news.error_message = ""
                    fetched_news.save()
                    if fetched_news.created_article:
                        self._update_article_from_draft(fetched_news.created_article, fetched_news, draft)
                        article_count += 1
                imported_count += 1

        if repair_articles:
            for article in Article.objects.all():
                values = [
                    article.title,
                    article.summary,
                    article.content,
                    article.meta_title,
                    article.meta_description,
                    article.meta_keywords,
                ]
                if not include_all and not any(has_mojibake(value) for value in values):
                    continue
                if not dry_run:
                    article.title = clean_text(article.title)
                    article.summary = clean_text(article.summary)
                    article.content = repair_mojibake(article.content)
                    article.meta_title = clean_text(article.meta_title)
                    article.meta_description = clean_text(article.meta_description)
                    article.meta_keywords = clean_text(article.meta_keywords)
                    article.save()
                article_count += 1

        mode = "DRY RUN: " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode}Repair complete. Imported rows: {imported_count}, articles: {article_count}"
            )
        )

    def _update_article_from_draft(self, article, fetched_news, draft):
        article.title = draft.ai_title
        article.summary = draft.ai_summary
        article.content = draft.ai_content
        article.source_name = draft.source_credit
        article.source_url = draft.source_url or fetched_news.original_url
        article.meta_title = draft.ai_title[:160]
        article.meta_description = draft.ai_summary[:220]
        article.meta_keywords = draft.seo_keywords
        article.save()
