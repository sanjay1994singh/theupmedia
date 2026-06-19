import uuid

from django.db import migrations
from django.template.defaultfilters import slugify
from django.utils import timezone


def fix_blank_article_slugs(apps, schema_editor):
    Article = apps.get_model("news", "Article")
    for article in Article.objects.filter(slug=""):
        base_slug = slugify(article.title)[:210] or f"news-{timezone.now():%Y%m%d}-{uuid.uuid4().hex[:8]}"
        slug = base_slug
        counter = 2
        while Article.objects.filter(slug=slug).exclude(pk=article.pk).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        article.slug = slug
        article.save(update_fields=["slug"])


class Migration(migrations.Migration):

    dependencies = [
        ("news", "0003_alter_article_content"),
    ]

    operations = [
        migrations.RunPython(fix_blank_article_slugs, migrations.RunPython.noop),
    ]
