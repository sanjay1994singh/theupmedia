from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand
from django.utils import timezone
from PIL import Image, ImageDraw
from pathlib import Path

from news.editorial_queue import build_long_form_article, generate_editorial_topics
from news.models import Article, Category
from news.slug_utils import seo_slugify, unique_article_slug


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
            summary = (
                f"{topic.title} पर यह विश्लेषण जनता की चिंता, नीति, भरोसे और आगे की संभावित दिशा को "
                "तथ्य-आधारित तरीके से समझाता है।"
            )[:220]
            article = Article(
                title=topic.title,
                slug=unique_article_slug(Article, topic.title),
                category=category,
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
            self._attach_thumbnail(article)
            created += 1

        self.stdout.write(self.style.SUCCESS(f"Created drafts: {created}, skipped duplicates: {skipped}"))

    def _attach_thumbnail(self, article):
        if article.featured_image:
            return
        thumb_dir = Path(settings.MEDIA_ROOT) / "articles" / "queue"
        thumb_dir.mkdir(parents=True, exist_ok=True)
        file_path = thumb_dir / f"queue-{article.pk}-thumb.jpg"
        image = Image.new("RGB", (1200, 675), "#111827")
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 1200, 675), fill="#111827")
        draw.rectangle((0, 0, 1200, 150), fill="#b91c1c")
        draw.rectangle((42, 190, 1158, 620), outline="#ef4444", width=7)
        draw.text((64, 48), "THE UP MEDIA", fill="#ffffff")
        draw.text((72, 238), article.title[:80], fill="#ffffff")
        draw.text((72, 548), article.category.name.upper(), fill="#fca5a5")
        image.save(file_path, "JPEG", quality=88, optimize=True)
        with file_path.open("rb") as image_file:
            article.featured_image.save(file_path.name, File(image_file), save=True)
