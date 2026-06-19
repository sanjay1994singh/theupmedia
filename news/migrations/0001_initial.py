import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Category",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True)),
                ("slug", models.SlugField(blank=True, max_length=140, unique=True)),
                ("description", models.TextField(blank=True)),
                ("meta_title", models.CharField(blank=True, max_length=160)),
                ("meta_description", models.CharField(blank=True, max_length=220)),
                ("image", models.ImageField(blank=True, null=True, upload_to="categories/")),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name_plural": "Categories",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="Article",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=220)),
                ("slug", models.SlugField(blank=True, max_length=240, unique=True)),
                ("summary", models.TextField(help_text="Short summary used on listing pages and search snippets.")),
                ("content", models.TextField()),
                ("featured_image", models.ImageField(blank=True, null=True, upload_to="articles/%Y/%m/")),
                ("image_alt_text", models.CharField(blank=True, max_length=180)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("published", "Published")], default="draft", max_length=20)),
                ("is_featured", models.BooleanField(default=False)),
                ("source_name", models.CharField(blank=True, max_length=120)),
                ("source_url", models.URLField(blank=True)),
                ("meta_title", models.CharField(blank=True, max_length=160)),
                ("meta_description", models.CharField(blank=True, max_length=220)),
                ("meta_keywords", models.CharField(blank=True, max_length=255)),
                ("canonical_url", models.URLField(blank=True)),
                ("published_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("author", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="articles", to=settings.AUTH_USER_MODEL)),
                ("category", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="articles", to="news.category")),
            ],
            options={
                "ordering": ["-published_at"],
                "indexes": [
                    models.Index(fields=["status", "-published_at"], name="news_articl_status_3401af_idx"),
                    models.Index(fields=["slug"], name="news_articl_slug_359fc3_idx"),
                    models.Index(fields=["is_featured", "-published_at"], name="news_articl_is_feat_c36d07_idx"),
                ],
            },
        ),
    ]
