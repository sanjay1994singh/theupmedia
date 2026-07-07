from django.contrib import admin
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import path, reverse
from django.utils.html import format_html

from .models import FacebookLiveSetting, LiveTVChannel, LiveTVSetting, MediaDownload, MobileAdminToken, MobileVideoUpload, SocialRenderedVideo


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

@admin.register(FacebookLiveSetting)
class FacebookLiveSettingAdmin(admin.ModelAdmin):
    list_display = ("name", "is_enabled", "status", "process_id", "started_at", "stopped_at", "updated_at")
    readonly_fields = ("control_buttons", "status", "process_id", "last_error", "started_at", "stopped_at", "updated_at")
    fieldsets = (
        ("Facebook RTMPS", {"fields": ("name", "is_enabled", "server_url", "stream_key")}),
        ("Controls", {"fields": ("control_buttons",)}),
        ("Status", {"fields": ("status", "process_id", "last_error", "started_at", "stopped_at", "updated_at")}),
    )

    def control_buttons(self, obj):
        if not obj or not obj.pk:
            return "Save first, then start Facebook Live."
        from .views import process_is_running

        is_live = process_is_running(obj.process_id) or obj.status in {FacebookLiveSetting.Status.STARTING, FacebookLiveSetting.Status.LIVE}
        action_url = reverse("admin:live_tv_facebooklivesetting_toggle", args=[obj.pk])
        if is_live:
            label = "Stop Facebook Live"
            color = "#b91c1c"
        else:
            label = "Start Facebook Live"
            color = "#159447"
        return format_html(
            '<a class="button" style="background:{};color:#fff;padding:8px 16px;border-radius:4px" href="{}">{}</a>'
            '<p style="margin-top:10px;color:#555">Save RTMPS settings first. Direct video/HLS source required; YouTube embed cannot be restreamed.</p>',
            color,
            action_url,
            label,
        )
    control_buttons.short_description = "Facebook Live Control"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path("<int:object_id>/toggle-facebook-live/", self.admin_site.admin_view(self.toggle_facebook_live), name="live_tv_facebooklivesetting_toggle"),
        ]
        return custom_urls + urls

    def toggle_facebook_live(self, request, object_id):
        setting = self.get_object(request, object_id)
        if not setting:
            self.message_user(request, "Facebook Live setting not found.", level=messages.ERROR)
            return redirect("admin:live_tv_facebooklivesetting_changelist")
        from .views import process_is_running, start_facebook_live_process, stop_facebook_live_process

        is_live = process_is_running(setting.process_id) or setting.status in {FacebookLiveSetting.Status.STARTING, FacebookLiveSetting.Status.LIVE}
        if is_live:
            stop_facebook_live_process(setting)
            self.message_user(request, "Facebook Live stop ho gaya.", level=messages.SUCCESS)
        else:
            try:
                start_facebook_live_process(setting)
                self.message_user(request, "Facebook Live start ho gaya.", level=messages.SUCCESS)
            except Exception as exc:
                setting.status = FacebookLiveSetting.Status.FAILED
                setting.last_error = str(exc)
                setting.process_id = None
                setting.save(update_fields=["status", "last_error", "process_id", "updated_at"])
                self.message_user(request, f"Facebook Live start failed: {exc}", level=messages.ERROR)
        return redirect(reverse("admin:live_tv_facebooklivesetting_change", args=[object_id]))

    def has_add_permission(self, request):
        return not FacebookLiveSetting.objects.exists()

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
