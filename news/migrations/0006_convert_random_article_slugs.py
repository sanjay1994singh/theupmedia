import re

from django.db import migrations
from news.slug_utils import seo_slugify


RANDOM_SLUG_PATTERN = re.compile(r"^news-\d{8}-[a-f0-9]{8}$")


def unique_slug(Article, title, pk):
    base_slug = seo_slugify(title) or f"news-{pk}"
    slug = base_slug[:240].strip("-")
    counter = 2
    while Article.objects.filter(slug=slug).exclude(pk=pk).exists():
        suffix = f"-{counter}"
        slug = f"{base_slug[:240 - len(suffix)]}{suffix}".strip("-")
        counter += 1
    return slug


def convert_random_slugs(apps, schema_editor):
    Article = apps.get_model("news", "Article")
    ArticleSlugRedirect = apps.get_model("news", "ArticleSlugRedirect")

    for article in Article.objects.all():
        if not RANDOM_SLUG_PATTERN.match(article.slug or ""):
            continue
        old_slug = article.slug
        new_slug = unique_slug(Article, article.title, article.pk)
        if not new_slug or new_slug == old_slug:
            continue
        article.slug = new_slug
        article.save(update_fields=["slug"])
        ArticleSlugRedirect.objects.get_or_create(old_slug=old_slug, defaults={"article_id": article.pk})


class Migration(migrations.Migration):

    dependencies = [
        ("news", "0005_alter_article_slug_articleslugredirect"),
    ]

    operations = [
        migrations.RunPython(convert_random_slugs, migrations.RunPython.noop),
    ]
