from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from news.article_defaults import get_default_author, get_or_make_location, infer_taxonomy
from news.editorial_queue import build_long_form_article, generate_editorial_topics
from news.models import Article, Category
from news.slug_utils import seo_slugify, unique_article_slug
from news.thumbnail_utils import attach_text_thumbnail


class Command(BaseCommand):
    help = "Create review-ready long-form draft articles for the editorial queue."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=100)
        parser.add_argument("--start-hours", type=int, default=2)
        parser.add_argument("--interval-hours", type=int, default=2)
        parser.add_argument("--apply", action="store_true", help="Create drafts. Without this, preview only.")

    def handle(self, *args, **options):
        count = max(1, min(options["count"], 100))
        start_at = timezone.now() + timezone.timedelta(hours=options["start_hours"])
        interval = timezone.timedelta(hours=options["interval_hours"])
        created = 0
        skipped = 0
        author = get_default_author() or get_user_model().objects.filter(is_superuser=True).order_by("id").first()

        for index, topic in enumerate(generate_editorial_topics(count)):
            published_at = start_at + (interval * index)
            self.stdout.write(f"{index + 1:03d}. draft scheduled -> {published_at:%Y-%m-%d %H:%M}")
            if not options["apply"]:
                continue

            if Article.objects.filter(title=topic.title).exists():
                skipped += 1
                continue

            category, _ = Category.objects.get_or_create(
                name=topic.category,
                defaults={"slug": seo_slugify(topic.category), "is_active": True},
            )
            inferred_category, state_name, city_name = infer_taxonomy(topic.title)
            if inferred_category:
                category, _ = Category.objects.get_or_create(
                    name=inferred_category,
                    defaults={"slug": seo_slugify(inferred_category), "is_active": True},
                )
            state, city = get_or_make_location(state_name, city_name)
            summary = (
                f"{topic.title} पर यह विश्लेषण जनता की चिंता, नीति, भरोसे और आगे की संभावित दिशा को "
                "तथ्य-आधारित तरीके से समझाता है।"
            )[:220]
            article = Article(
                title=topic.title,
                slug=unique_article_slug(Article, topic.title),
                category=category,
                state=state,
                city=city,
                author=author,
                summary=summary,
                content=build_long_form_article(topic),
                status=Article.Status.DRAFT,
                published_at=published_at,
                source_name=topic.reference_name,
                source_url=topic.reference_url,
                image_alt_text=topic.title[:180],
                image_caption=f"{topic.title} से जुड़ी प्रतीकात्मक तस्वीर",
                image_credit="The Up Media",
                meta_title=topic.title[:160],
                meta_description=summary,
                meta_keywords=", ".join(
                    [
                        topic.category,
                        "The Up Media",
                        "Hindi analysis",
                        "public interest",
                        "India news",
                    ]
                ),
            )
            article.save()
            if author:
                article.reviewed_by = article.reviewed_by or author
                article.fact_checked_by = article.fact_checked_by or author
                article.save()
            attach_text_thumbnail(article, folder="queue", prefix="queue")
            created += 1

        self.stdout.write(self.style.SUCCESS(f"Created drafts: {created}, skipped duplicates: {skipped}"))
