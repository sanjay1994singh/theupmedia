from django.contrib import admin

from .models import BlogPost


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "is_featured", "author", "published_at", "updated_at")
    list_filter = ("status", "is_featured", "published_at")
    search_fields = ("title", "excerpt", "content", "focus_keyword", "meta_keywords")
    prepopulated_fields = {"slug": ("title",)}
    date_hierarchy = "published_at"
    fieldsets = (
        ("Blog", {"fields": ("title", "slug", "author", "excerpt", "content", "featured_image", "image_alt_text")}),
        ("Publishing", {"fields": ("status", "is_featured", "published_at")}),
        ("SEO", {"fields": ("focus_keyword", "meta_title", "meta_description", "meta_keywords", "canonical_url")}),
    )
