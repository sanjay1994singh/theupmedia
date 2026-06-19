from django.contrib import admin

from .models import Article, Category, City, State


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("name", "state", "slug", "is_active", "created_at")
    list_filter = ("state", "is_active")
    search_fields = ("name", "state__name", "description")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "state", "city", "author", "status", "is_featured", "published_at")
    list_filter = ("status", "is_featured", "category", "state", "city", "published_at")
    search_fields = ("title", "summary", "content", "meta_keywords", "state__name", "city__name")
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("state", "city", "author")
    date_hierarchy = "published_at"
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Article", {"fields": ("title", "slug", "category", "state", "city", "author", "summary", "content", "featured_image", "image_alt_text")}),
        ("Publishing", {"fields": ("status", "is_featured", "published_at", "source_name", "source_url")}),
        ("SEO", {"fields": ("meta_title", "meta_description", "meta_keywords", "canonical_url")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    def _can_manage_articles(self, request):
        user = request.user
        if user.is_superuser:
            return True
        if getattr(user, "role", "reader") in {"admin", "editor", "author"}:
            return True
        return any(
            [
                getattr(user, "is_author", False),
                getattr(user, "is_editor", False),
                getattr(user, "is_reporter", False),
            ]
        )

    def has_add_permission(self, request):
        return super().has_add_permission(request) and self._can_manage_articles(request)

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and self._can_manage_articles(request)

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and self._can_manage_articles(request)

    def save_model(self, request, obj, form, change):
        if not obj.author_id:
            obj.author = request.user
        super().save_model(request, obj, form, change)
