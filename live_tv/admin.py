from django.contrib import admin

from .models import LiveTVChannel, LiveTVSetting, MediaDownload, MobileAdminToken, MobileVideoUpload, SocialRenderedVideo


@admin.register(LiveTVChannel)
class LiveTVChannelAdmin(admin.ModelAdmin):
    list_display = ("title", "source_type", "is_live", "is_active", "display_order", "updated_at")
    list_filter = ("source_type", "is_live", "is_active")
    search_fields = ("title", "headline", "ticker_text")
    prepopulated_fields = {"slug": ("title",)}
    list_editable = ("is_live", "is_active", "display_order")
    fieldsets = (
        ("Basic", {"fields": ("title", "slug", "description", "is_active", "is_live", "display_order")}),
        ("Video Source", {"fields": ("source_type", "youtube_url", "stream_url", "video_file", "poster_image")}),
        ("Video Text", {"fields": ("lower_third_label", "headline", "ticker_label", "ticker_text")}),
        ("SEO", {"fields": ("meta_title", "meta_description")}),
    )



@admin.register(LiveTVSetting)
class LiveTVSettingAdmin(admin.ModelAdmin):
    list_display = ("name", "live_label", "ticker_speed_seconds", "mobile_ticker_speed_seconds", "show_live_badge", "show_channel_logo", "show_lower_third", "show_ticker", "updated_at")
    fieldsets = (
        ("Branding", {"fields": ("name", "live_label", "channel_logo", "autoplay")}),
        ("Frame Visibility", {"fields": ("show_live_badge", "show_channel_logo", "show_lower_third", "show_ticker")}),
        ("Default Video Text", {"fields": ("default_lower_third_label", "default_headline", "default_ticker_label", "default_ticker_text", "ticker_speed_seconds", "mobile_ticker_speed_seconds")}),
    )

    def has_add_permission(self, request):
        return not LiveTVSetting.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
@admin.register(MobileVideoUpload)
class MobileVideoUploadAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "uploaded_by_name", "uploaded_by_phone", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("title", "description", "uploaded_by_name", "uploaded_by_phone")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Video", {"fields": ("title", "description", "video", "status")}),
        ("Uploader", {"fields": ("uploaded_by_name", "uploaded_by_phone", "device_info")}),
        ("Dates", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(MobileAdminToken)
class MobileAdminTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "device_name", "created_at", "last_used_at")
    list_filter = ("created_at", "last_used_at")
    search_fields = ("user__username", "user__email", "device_name")
    readonly_fields = ("key", "created_at", "last_used_at")



@admin.register(MediaDownload)
class MediaDownloadAdmin(admin.ModelAdmin):
    list_display = ("title", "media_type", "status", "progress_percent", "created_by", "created_at")
    list_filter = ("status", "media_type", "created_at")
    search_fields = ("title", "source_url")
    readonly_fields = ("progress_percent", "created_at", "updated_at", "error_message")
@admin.register(SocialRenderedVideo)
class SocialRenderedVideoAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "progress_percent", "created_by", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("title", "headline", "ticker_text")
    readonly_fields = ("progress_percent", "created_at", "updated_at", "error_message")
