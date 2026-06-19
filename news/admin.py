from django.contrib import admin

from .models import Article, Category


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "author", "status", "is_featured", "published_at")
    list_filter = ("status", "is_featured", "category", "published_at")
    search_fields = ("title", "summary", "content", "meta_keywords")
    prepopulated_fields = {"slug": ("title",)}
    date_hierarchy = "published_at"
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Article", {"fields": ("title", "slug", "category", "author", "summary", "content", "featured_image", "image_alt_text")}),
        ("Publishing", {"fields": ("status", "is_featured", "published_at", "source_name", "source_url")}),
        ("SEO", {"fields": ("meta_title", "meta_description", "meta_keywords", "canonical_url")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
