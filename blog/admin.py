from django.contrib import admin

from .models import BlogPost


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "is_featured", "views_count", "author")
    list_filter = ("status", "is_featured")
    search_fields = ("title", "excerpt", "content", "focus_keyword", "meta_keywords")
    prepopulated_fields = {"slug": ("title",)}
    ordering = ("-id",)
    fieldsets = (
        ("Blog", {"fields": ("title", "slug", "author", "excerpt", "content", "featured_image", "image_alt_text")}),
        ("Publishing", {"fields": ("status", "is_featured", "views_count", "published_at")}),
        ("SEO", {"fields": ("focus_keyword", "meta_title", "meta_description", "meta_keywords", "canonical_url")}),
    )
    readonly_fields = ("views_count",)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.resolver_match and request.resolver_match.url_name == "blog_blogpost_changelist":
            return queryset.defer("published_at", "updated_at", "created_at")
        return queryset
