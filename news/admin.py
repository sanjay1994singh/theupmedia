import json

from django.contrib import admin, messages
from django.utils import timezone

from .models import Article, ArticleRead, ArticleSlugRedirect, Category, City, FetchedNews, NewsSource, State
from .services.ai_writer import build_hindi_news_draft, clean_text, repair_mojibake
from .services.social_hooks import notify_facebook_page, run_publish_hooks


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
    list_display = (
        "title",
        "category",
        "state",
        "city",
        "author",
        "status",
        "is_featured",
        "unique_reads",
        "facebook_posted_at",
        "published_at",
    )
    list_filter = ("status", "is_featured", "category", "state", "city")
    search_fields = ("title", "summary", "content", "meta_keywords", "state__name", "city__name")
    autocomplete_fields = ("state", "city", "author")
    readonly_fields = ("unique_reads", "facebook_post_id", "facebook_posted_at", "facebook_post_error", "created_at", "updated_at")
    actions = ("repair_hindi_encoding", "post_selected_to_facebook")
    fieldsets = (
        ("Article", {"fields": ("title", "slug", "category", "state", "city", "author", "summary", "content", "featured_image", "image_alt_text")}),
        ("Publishing", {"fields": ("status", "is_featured", "published_at", "source_name", "source_url")}),
        ("Facebook Auto Post", {"fields": ("facebook_post_id", "facebook_posted_at", "facebook_post_error")}),
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
        old_status = None
        if obj.pk:
            old_status = Article.objects.filter(pk=obj.pk).values_list("status", flat=True).first()
        if not obj.author_id:
            obj.author = request.user
        if obj.status == Article.Status.PUBLISHED and old_status != Article.Status.PUBLISHED:
            obj.published_at = timezone.now()
        super().save_model(request, obj, form, change)
        became_published = obj.status == Article.Status.PUBLISHED and old_status != Article.Status.PUBLISHED
        if became_published:
            result = notify_facebook_page(obj)
            if result.get("sent"):
                self.message_user(request, "Article auto-posted to Facebook Page.", messages.SUCCESS)
            elif result.get("skipped"):
                self.message_user(request, "Facebook auto-post skipped because this article was already posted.", messages.INFO)
            else:
                self.message_user(
                    request,
                    f"Article published, but Facebook auto-post failed: {result.get('reason') or result.get('response')}",
                    messages.WARNING,
                )

    @admin.action(description="Repair Hindi encoding for selected articles")
    def repair_hindi_encoding(self, request, queryset):
        updated = 0
        for article in queryset:
            article.title = clean_text(article.title)
            article.summary = clean_text(article.summary)
            article.content = repair_mojibake(article.content)
            article.meta_title = clean_text(article.meta_title)
            article.meta_description = clean_text(article.meta_description)
            article.meta_keywords = clean_text(article.meta_keywords)
            article.save()
            updated += 1
        self.message_user(request, f"Hindi encoding repaired for {updated} article(s).", messages.INFO)

    @admin.action(description="Post selected published articles to Facebook")
    def post_selected_to_facebook(self, request, queryset):
        posted = 0
        skipped = 0
        failed = 0
        for article in queryset:
            if article.status != Article.Status.PUBLISHED:
                skipped += 1
                continue
            if article.published_at > timezone.now():
                article.published_at = timezone.now()
                article.save(update_fields=["published_at", "updated_at"])
            result = notify_facebook_page(article)
            if result.get("sent"):
                posted += 1
            elif result.get("skipped"):
                skipped += 1
            else:
                failed += 1
        self.message_user(request, f"Facebook posting complete. Posted: {posted}, skipped: {skipped}, failed: {failed}", messages.INFO)


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
    actions = (
        "regenerate_ai_drafts",
        "repair_text_and_update_articles",
        "create_article_drafts",
        "publish_imports",
        "run_social_share_hooks",
    )
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

    @admin.action(description="Regenerate AI fields for selected pending imports")
    def regenerate_ai_drafts(self, request, queryset):
        updated = 0
        skipped = 0
        for fetched_news in queryset.select_related("source"):
            if fetched_news.created_article_id or fetched_news.status == FetchedNews.Status.PUBLISHED:
                skipped += 1
                continue
            draft = build_hindi_news_draft(
                original_title=fetched_news.original_title,
                original_summary=fetched_news.original_summary,
                source_name=fetched_news.source.name,
                source_url=fetched_news.original_url,
            )
            fetched_news.ai_title = draft.ai_title
            fetched_news.ai_summary = draft.ai_summary
            fetched_news.ai_content = draft.ai_content
            fetched_news.ai_slug = draft.slug
            fetched_news.source_credit = draft.source_credit
            fetched_news.source_url = draft.source_url
            fetched_news.fact_points = json.dumps(draft.fact_points, ensure_ascii=False)
            fetched_news.seo_keywords = draft.seo_keywords
            fetched_news.internal_note = draft.internal_note
            fetched_news.status = FetchedNews.Status.PENDING
            fetched_news.error_message = ""
            fetched_news.save()
            updated += 1
        self.message_user(request, f"AI regenerated: {updated}, skipped locked/published: {skipped}", messages.INFO)

    @admin.action(description="Repair Hindi text and update linked Articles")
    def repair_text_and_update_articles(self, request, queryset):
        updated_imports = 0
        updated_articles = 0
        for fetched_news in queryset.select_related("source", "created_article"):
            original_title = clean_text(fetched_news.original_title)
            original_summary = clean_text(fetched_news.original_summary)
            draft = build_hindi_news_draft(
                original_title=original_title,
                original_summary=original_summary,
                source_name=fetched_news.source.name,
                source_url=fetched_news.original_url,
            )
            fetched_news.original_title = original_title[:300]
            fetched_news.original_summary = original_summary
            fetched_news.ai_title = draft.ai_title
            fetched_news.ai_summary = draft.ai_summary
            fetched_news.ai_content = draft.ai_content
            fetched_news.ai_slug = draft.slug
            fetched_news.source_credit = draft.source_credit
            fetched_news.source_url = draft.source_url
            fetched_news.fact_points = json.dumps(draft.fact_points, ensure_ascii=False)
            fetched_news.seo_keywords = draft.seo_keywords
            fetched_news.internal_note = draft.internal_note
            fetched_news.error_message = ""
            fetched_news.save()
            updated_imports += 1

            article = fetched_news.created_article
            if article:
                article.title = draft.ai_title
                article.summary = draft.ai_summary
                article.content = draft.ai_content
                article.source_name = draft.source_credit
                article.source_url = draft.source_url or fetched_news.original_url
                article.meta_title = draft.ai_title[:160]
                article.meta_description = draft.ai_summary[:220]
                article.meta_keywords = draft.seo_keywords
                article.save()
                updated_articles += 1
        self.message_user(
            request,
            f"Text repaired. Imports updated: {updated_imports}, linked articles updated: {updated_articles}",
            messages.INFO,
        )

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
