from django.contrib import admin, messages
from django.utils import timezone

from .models import Article, ArticleRead, ArticleSlugRedirect, Category, City, FetchedNews, NewsSource, State
from .services.social_hooks import run_publish_hooks


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
    list_display = ("title", "category", "state", "city", "author", "status", "is_featured", "unique_reads", "published_at")
    list_filter = ("status", "is_featured", "category", "state", "city")
    search_fields = ("title", "summary", "content", "meta_keywords", "state__name", "city__name")
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("state", "city", "author")
    readonly_fields = ("unique_reads", "created_at", "updated_at")
    fieldsets = (
        ("Article", {"fields": ("title", "slug", "category", "state", "city", "author", "summary", "content", "featured_image", "image_alt_text")}),
        ("Publishing", {"fields": ("status", "is_featured", "published_at", "source_name", "source_url")}),
        ("Analytics", {"fields": ("unique_reads",)}),
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


@admin.register(NewsSource)
class NewsSourceAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "is_active", "rss_url", "updated_at")
    list_filter = ("is_active", "category")
    search_fields = ("name", "rss_url", "category__name")
    autocomplete_fields = ("category",)


@admin.register(FetchedNews)
class FetchedNewsAdmin(admin.ModelAdmin):
    list_display = ("original_title", "source", "status", "created_article", "fetched_at")
    list_filter = ("status", "source", "source__category", "fetched_at")
    search_fields = ("original_title", "original_summary", "ai_title", "ai_summary", "original_url", "source_credit", "source_url")
    autocomplete_fields = ("source", "created_article")
    readonly_fields = ("fetched_at", "updated_at")
    actions = ("create_article_drafts", "publish_imports", "run_social_share_hooks")
    fieldsets = (
        ("Source", {"fields": ("source", "original_title", "original_url", "original_summary")}),
        ("AI Draft", {"fields": ("ai_title", "ai_summary", "ai_content", "ai_slug", "fact_points", "seo_keywords")}),
        ("Source Credit", {"fields": ("source_credit", "source_url")}),
        ("Workflow", {"fields": ("status", "created_article", "internal_note", "error_message")}),
        ("Timestamps", {"fields": ("fetched_at", "updated_at")}),
    )

    def _create_article_from_import(self, fetched_news, status, author=None):
        if fetched_news.created_article:
            article = fetched_news.created_article
            article.status = status
            if status == Article.Status.PUBLISHED:
                article.published_at = timezone.now()
            article.save()
            fetched_news.status = FetchedNews.Status.PUBLISHED if status == Article.Status.PUBLISHED else FetchedNews.Status.DRAFT
            fetched_news.save(update_fields=["status", "updated_at"])
            return article, False

        category = fetched_news.source.category
        if not category:
            raise ValueError("Source category is required before creating an article.")

        article = Article.objects.create(
            title=fetched_news.ai_title or fetched_news.original_title,
            slug="",
            category=category,
            author=author,
            summary=fetched_news.ai_summary or fetched_news.original_summary[:220],
            content=fetched_news.ai_content,
            status=status,
            source_name=fetched_news.source_credit or fetched_news.source.name,
            source_url=fetched_news.source_url or fetched_news.original_url,
            meta_title=(fetched_news.ai_title or fetched_news.original_title)[:160],
            meta_description=(fetched_news.ai_summary or fetched_news.original_summary)[:220],
            meta_keywords=fetched_news.seo_keywords,
            canonical_url="",
            published_at=timezone.now(),
        )
        fetched_news.created_article = article
        fetched_news.status = FetchedNews.Status.PUBLISHED if status == Article.Status.PUBLISHED else FetchedNews.Status.DRAFT
        fetched_news.error_message = ""
        fetched_news.save(update_fields=["created_article", "status", "error_message", "updated_at"])
        return article, True

    @admin.action(description="Create Article drafts from selected imports")
    def create_article_drafts(self, request, queryset):
        created = 0
        failed = 0
        for fetched_news in queryset.select_related("source", "source__category", "created_article"):
            try:
                _, was_created = self._create_article_from_import(fetched_news, Article.Status.DRAFT, request.user)
                created += int(was_created)
            except ValueError as exc:
                failed += 1
                fetched_news.status = FetchedNews.Status.FAILED
                fetched_news.error_message = str(exc)
                fetched_news.save(update_fields=["status", "error_message", "updated_at"])
        self.message_user(request, f"Draft action complete. New drafts: {created}, failed: {failed}", messages.INFO)

    @admin.action(description="Approve and publish selected imports")
    def publish_imports(self, request, queryset):
        published = 0
        failed = 0
        for fetched_news in queryset.select_related("source", "source__category", "created_article"):
            try:
                article, _ = self._create_article_from_import(fetched_news, Article.Status.PUBLISHED, request.user)
                published += 1
                run_publish_hooks(article)
            except ValueError as exc:
                failed += 1
                fetched_news.status = FetchedNews.Status.FAILED
                fetched_news.error_message = str(exc)
                fetched_news.save(update_fields=["status", "error_message", "updated_at"])
        self.message_user(request, f"Publish action complete. Published: {published}, failed: {failed}", messages.INFO)

    @admin.action(description="Run social share hooks for published imported articles")
    def run_social_share_hooks(self, request, queryset):
        triggered = 0
        for fetched_news in queryset.select_related("created_article"):
            if fetched_news.created_article and fetched_news.created_article.status == Article.Status.PUBLISHED:
                run_publish_hooks(fetched_news.created_article)
                triggered += 1
        self.message_user(request, f"Social hook placeholders triggered for {triggered} article(s).", messages.INFO)


@admin.register(ArticleSlugRedirect)
class ArticleSlugRedirectAdmin(admin.ModelAdmin):
    list_display = ("old_slug", "article", "created_at")
    search_fields = ("old_slug", "article__title", "article__slug")
    autocomplete_fields = ("article",)
    readonly_fields = ("created_at",)


@admin.register(ArticleRead)
class ArticleReadAdmin(admin.ModelAdmin):
    list_display = ("article", "user", "ip_address", "first_read_at", "last_read_at")
    list_filter = ("first_read_at", "last_read_at")
    search_fields = ("article__title", "article__slug", "user__username", "ip_address", "fingerprint")
    readonly_fields = ("article", "user", "fingerprint", "session_key", "ip_address", "user_agent_hash", "first_read_at", "last_read_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
