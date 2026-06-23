from django.contrib import admin

from .models import LiveTVChannel


@admin.register(LiveTVChannel)
class LiveTVChannelAdmin(admin.ModelAdmin):
    list_display = ("title", "source_type", "is_live", "is_active", "display_order", "updated_at")
    list_filter = ("source_type", "is_live", "is_active", "show_lower_third", "show_ticker")
    search_fields = ("title", "headline", "ticker_text")
    prepopulated_fields = {"slug": ("title",)}
    list_editable = ("is_live", "is_active", "display_order")
    fieldsets = (
        ("Basic", {"fields": ("title", "slug", "description", "is_active", "is_live", "display_order")}),
        ("Video Source", {"fields": ("source_type", "youtube_url", "stream_url", "video_file", "poster_image", "autoplay")}),
        ("Graphics Overlay", {"fields": ("channel_logo", "show_channel_logo", "show_lower_third", "lower_third_label", "headline", "show_ticker", "ticker_label", "ticker_text")}),
        ("SEO", {"fields": ("meta_title", "meta_description")}),
    )
