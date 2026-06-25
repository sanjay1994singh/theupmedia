import json

from django.core.management.base import BaseCommand
from django.db import IntegrityError
from django.utils import timezone

from news.models import FetchedNews, NewsSource
from news.services.ai_writer import build_hindi_news_draft, clean_text
from news.services.rss_fetcher import fetch_source_items


class Command(BaseCommand):
    help = "Fetch active RSS sources and store AI-assisted Hindi news drafts as pending imports."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=20, help="Maximum feed items per source.")
        parser.add_argument("--source-id", type=int, default=None, help="Fetch only one source id.")
        parser.add_argument("--timeout", type=int, default=15, help="RSS request timeout in seconds.")

    def handle(self, *args, **options):
        limit = max(1, min(options["limit"], 50))
        timeout = max(3, options["timeout"])
        sources = NewsSource.objects.filter(is_active=True)
        if options["source_id"]:
            sources = sources.filter(pk=options["source_id"])

        created_count = 0
        skipped_count = 0
        failed_count = 0

        for source in sources.select_related("category"):
            items, error = fetch_source_items(source, limit=limit, timeout=timeout)
            if error:
                failed_count += 1
                self.stderr.write(self.style.WARNING(f"{source.name}: {error}"))
                continue

            for item in items:
                if FetchedNews.objects.filter(original_url=item.url).exists():
                    skipped_count += 1
                    continue

                try:
                    original_title = clean_text(item.title)
                    original_summary = clean_text(item.summary)
                    draft = build_hindi_news_draft(
                        original_title=original_title,
                        original_summary=original_summary,
                        source_name=source.name,
                        source_url=item.url,
                    )
                    FetchedNews.objects.create(
                        source=source,
                        original_title=original_title[:300],
                        original_url=item.url,
                        original_summary=original_summary,
                        ai_title=draft.ai_title,
                        ai_summary=draft.ai_summary,
                        ai_content=draft.ai_content,
                        ai_slug=draft.slug,
                        source_credit=draft.source_credit,
                        source_url=draft.source_url,
                        fact_points=json.dumps(draft.fact_points, ensure_ascii=False),
                        seo_keywords=draft.seo_keywords,
                        internal_note=draft.internal_note,
                        status=FetchedNews.Status.PENDING,
                        fetched_at=item.published_at or timezone.now(),
                    )
                    created_count += 1
                except IntegrityError:
                    skipped_count += 1
                except Exception as exc:
                    failed_count += 1
                    FetchedNews.objects.update_or_create(
                        original_url=item.url,
                        defaults={
                            "source": source,
                            "original_title": clean_text(item.title)[:300],
                            "original_summary": clean_text(item.summary),
                            "status": FetchedNews.Status.FAILED,
                            "error_message": str(exc),
                            "source_credit": source.name,
                            "source_url": item.url,
                            "internal_note": "Draft generated from source facts; editor review required.",
                            "fetched_at": item.published_at or timezone.now(),
                        },
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"Fetch complete. Created: {created_count}, skipped duplicates: {skipped_count}, failed sources: {failed_count}"
            )
        )
