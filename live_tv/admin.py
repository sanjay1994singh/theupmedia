from django.contrib import admin
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import redirect
from django.urls import path, reverse
from django.utils.html import format_html

from .models import AppHomeSetting, AppMenu, ChannelFollow, FacebookLiveSetting, HomeContent, HomeUtility, LiveTVCategory, LiveTVCity, LiveTVChannel, LiveTVPlaylistCycle, LiveTVPlaylistItem, LiveTVSetting, LiveTVState, MediaDownload, MobileAdminToken, NewsTickerSetting, ShortsComment, ShortsLike, ShortsVideo, SocialRenderedVideo
from .services import calculate_current_playback, update_playlist_item


@admin.register(AppMenu)
class AppMenuAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "target_type", "target_value", "display_order", "is_active")
    list_editable = ("display_order", "is_active")
    prepopulated_fields = {"slug": ("title",)}
    search_fields = ("title", "target_value")


@admin.register(HomeContent)
class HomeContentAdmin(admin.ModelAdmin):
    list_display = ("title", "section", "stream_type", "badge_text", "display_order", "is_active", "updated_at")
    list_filter = ("section", "stream_type", "is_active")
    list_editable = ("display_order", "is_active")
    search_fields = ("title", "subtitle", "badge_text")
    fieldsets = (
        ("Section", {"fields": ("section", "title", "subtitle", "badge_text", "display_order", "is_active")}),
        ("Media", {"fields": ("thumbnail", "image_url", "stream_type", "video_url", "youtube_url", "duration", "viewers_count")}),
    )


@admin.register(HomeUtility)
class HomeUtilityAdmin(admin.ModelAdmin):
    list_display = ("title", "icon", "action", "display_order", "is_active")
    list_editable = ("display_order", "is_active")
    search_fields = ("title", "subtitle", "action")


@admin.register(AppHomeSetting)
class AppHomeSettingAdmin(admin.ModelAdmin):
    list_display = ("title", "hero_badge", "hero_button_text", "updated_at")
    fieldsets = (
        ("Home Header", {"fields": ("title", "subtitle", "logo")}),
        ("Live TV Hero", {"fields": ("hero_badge", "hero_button_text")}),
    )

    def has_add_permission(self, request):
        return not AppHomeSetting.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LiveTVCategory)
class LiveTVCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "display_order", "is_active")
    list_editable = ("display_order", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(LiveTVState)
class LiveTVStateAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "display_order", "is_active")
    list_editable = ("display_order", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(LiveTVCity)
class LiveTVCityAdmin(admin.ModelAdmin):
    list_display = ("name", "state", "slug", "display_order", "is_active")
    list_filter = ("state", "is_active")
    list_editable = ("display_order", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "state__name")


@admin.register(LiveTVChannel)
class LiveTVChannelAdmin(admin.ModelAdmin):
    list_display = ("title", "channel_role", "source_type", "hls_status", "playlist_duration_display", "is_live", "is_active", "display_order", "updated_at")
    list_filter = ("source_type", "auto_playlist_enabled", "auto_add_to_live", "hls_status", "is_live", "is_active")
    search_fields = ("title", "headline", "ticker_text", "city__name", "state__name", "category__name")
    prepopulated_fields = {"slug": ("title",)}
    list_editable = ("is_live", "is_active", "display_order")
    readonly_fields = ("hls_master_url", "hls_status", "processing_error", "duration", "duration_seconds", "current_playback_display", "playlist_duration_display", "playlist_target_progress", "playlist_version", "playback_started_at", "last_playlist_update", "processing_failures")
    fieldsets = (
        ("Basic", {"fields": ("title", "slug", "description", "is_active", "is_live", "display_order")}),
        ("Video Source", {"fields": ("source_type", "youtube_url", "stream_url", "video_file", "poster_image")}),
        ("HLS Processing", {"fields": ("hls_master_url", "hls_status", "processing_error", "duration", "duration_seconds")}),
        ("24x7 Auto Playlist", {"fields": ("auto_playlist_enabled", "auto_add_to_live", "loop_enabled", "target_playlist_duration_seconds", "current_playback_display", "playlist_duration_display", "playlist_target_progress", "playlist_version", "playback_started_at", "last_playlist_update", "processing_failures")}),
        ("Category / Location", {"fields": ("category", "state", "city")}),
        ("Video Text", {"fields": ("lower_third_label", "headline")}),
        ("SEO", {"fields": ("meta_title", "meta_description")}),
    )

    def save_model(self, request, obj, form, change):
        video_changed = "video_file" in form.changed_data
        if obj.source_type == LiveTVChannel.SourceType.DIRECT and obj.video_file and video_changed:
            obj.hls_master_url = ""
            obj.hls_status = LiveTVChannel.HLSStatus.PENDING
            obj.processing_error = ""
            obj.duration = None
            obj.duration_seconds = 0
        super().save_model(request, obj, form, change)
        if obj.source_type == LiveTVChannel.SourceType.DIRECT and obj.video_file and video_changed:
            from .views import enqueue_live_channel_hls_job

            transaction.on_commit(lambda: enqueue_live_channel_hls_job(obj.pk))

    def _safe_related_name(self, obj, field_name, id_field_name):
        raw_id = getattr(obj, id_field_name, None)
        if raw_id in (None, ""):
            return "-"
        try:
            related = getattr(obj, field_name)
            return str(related) if related else "-"
        except (ValueError, TypeError, LiveTVCategory.DoesNotExist, LiveTVState.DoesNotExist, LiveTVCity.DoesNotExist):
            return f"Invalid ID: {raw_id}"

    def safe_category(self, obj):
        return self._safe_related_name(obj, "category", "category_id")

    safe_category.short_description = "Category"

    def safe_state(self, obj):
        return self._safe_related_name(obj, "state", "state_id")

    safe_state.short_description = "State"

    def safe_city(self, obj):
        return self._safe_related_name(obj, "city", "city_id")

    safe_city.short_description = "City"

    @admin.display(description="Role")
    def channel_role(self, obj):
        return "Main playlist channel" if obj.auto_playlist_enabled else "Uploaded video/source"

    @admin.display(description="Playlist duration")
    def playlist_duration_display(self, obj):
        if not obj.auto_playlist_enabled:
            return "-"
        return f"{obj.playlist_duration_minutes:.2f} min ({obj.playlist_duration_seconds} sec)"

    @admin.display(description="Target progress")
    def playlist_target_progress(self, obj):
        target = max(1, obj.target_playlist_duration_seconds)
        return f"{min(100, (obj.playlist_duration_seconds / target) * 100):.1f}% of {target // 60} min"

    @admin.display(description="Current / next")
    def current_playback_display(self, obj):
        if not obj.auto_playlist_enabled:
            return "-"
        state = calculate_current_playback(obj)
        if not state:
            return "Playlist is empty"
        current = state["video"].title
        next_title = state["next_entry"].video.title if state.get("next_entry") else "-"
        return f"{current} at {state['seek_position']:.1f}s; next: {next_title}"

    @admin.display(description="Processing failures")
    def processing_failures(self, obj):
        if not obj.auto_playlist_enabled:
            return "-"
        return LiveTVChannel.objects.filter(hls_status=LiveTVChannel.HLSStatus.FAILED, auto_add_to_live=True).count()


@admin.register(LiveTVPlaylistItem)
class LiveTVPlaylistItemAdmin(admin.ModelAdmin):
    list_display = ("position_display", "channel", "video", "duration_seconds", "priority", "source_status", "is_active", "playlist_controls")
    list_filter = ("channel", "priority", "is_active", "video__hls_status")
    search_fields = ("channel__title", "video__title", "video__headline")
    readonly_fields = ("added_at", "removed_at", "created_at", "updated_at")
    autocomplete_fields = ("channel", "video")

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<int:object_id>/playlist-action/<str:action>/",
                self.admin_site.admin_view(self.playlist_action),
                name="live_tv_playlist_action",
            )
        ]
        return custom + urls

    def playlist_action(self, request, object_id, action):
        item = self.get_object(request, object_id)
        if not item:
            messages.error(request, "Playlist item not found.")
            return redirect("admin:live_tv_livetvplaylistitem_changelist")
        try:
            update_playlist_item(item, action)
            messages.success(request, f"Playlist action completed: {action.replace('_', ' ')}")
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        return redirect("admin:live_tv_livetvplaylistitem_changelist")

    @admin.display(description="#", ordering="position")
    def position_display(self, obj):
        return obj.position + 1

    @admin.display(description="Video status")
    def source_status(self, obj):
        return f"{obj.video.get_hls_status_display()} / {'active' if obj.video.is_active else 'inactive'}"

    @admin.display(description="Controls")
    def playlist_controls(self, obj):
        actions = [("move_up", "Up"), ("move_down", "Down")]
        actions.append(("remove", "Remove") if obj.is_active else ("restore", "Restore"))
        if obj.is_active:
            actions.extend([("next", "Play next"), ("immediate", "Play now")])
        links = []
        for action, label in actions:
            url = reverse("admin:live_tv_playlist_action", args=[obj.pk, action])
            links.append(format_html('<a href="{}">{}</a>', url, label))
        return format_html(" &nbsp; ".join("{}" for _ in links), *links)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LiveTVPlaylistCycle)
class LiveTVPlaylistCycleAdmin(admin.ModelAdmin):
    list_display = ("channel", "version", "starts_at", "total_duration_seconds", "created_at")
    list_filter = ("channel",)
    readonly_fields = ("channel", "version", "starts_at", "total_duration_seconds", "created_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False



@admin.register(LiveTVSetting)
class LiveTVSettingAdmin(admin.ModelAdmin):
    list_display = ("name", "live_label", "show_live_badge", "show_channel_logo", "show_lower_third", "show_ticker", "updated_at")
    fieldsets = (
        ("Branding", {"fields": ("name", "live_label", "channel_logo", "autoplay")}),
        ("Frame Visibility", {"fields": ("show_live_badge", "show_channel_logo", "show_lower_third", "show_ticker")}),
        ("Default Video Text", {"fields": ("default_lower_third_label", "default_headline")}),
    )

    def has_add_permission(self, request):
        return not LiveTVSetting.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(FacebookLiveSetting)
class FacebookLiveSettingAdmin(admin.ModelAdmin):
    list_display = ("name", "is_enabled", "status", "process_id", "started_at", "stopped_at", "updated_at")
    readonly_fields = ("control_buttons", "status", "process_id", "last_error", "ffmpeg_log_tail", "started_at", "stopped_at", "updated_at")
    fieldsets = (
        ("Facebook RTMPS", {"fields": ("name", "is_enabled", "server_url", "stream_key")}),
        ("Controls", {"fields": ("control_buttons",)}),
        ("Status", {"fields": ("status", "process_id", "last_error", "ffmpeg_log_tail", "started_at", "stopped_at", "updated_at")}),
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

    def ffmpeg_log_tail(self, obj):
        if not obj or not obj.log_file:
            return "-"
        from .views import tail_file

        return tail_file(obj.log_file, max_chars=4000) or "-"
    ffmpeg_log_tail.short_description = "Recent FFmpeg/Facebook Log"


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

@admin.register(NewsTickerSetting)
class NewsTickerSettingAdmin(admin.ModelAdmin):
    list_display = ("label", "speed_seconds", "mobile_speed_seconds", "style", "updated_at")
    fieldsets = (
        ("Ticker", {"fields": ("label", "text", "style")}),
        ("Speed", {"fields": ("speed_seconds", "mobile_speed_seconds")}),
    )

    def has_add_permission(self, request):
        return not NewsTickerSetting.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ShortsVideo)
class ShortsVideoAdmin(admin.ModelAdmin):
    list_display = ("title", "frame_template", "category", "state", "city", "location", "hls_status", "is_published", "display_order", "views_count", "likes_count", "comments_count", "shares_count", "created_at")
    list_filter = ("is_published", "hls_status", "frame_template")
    search_fields = ("title", "headline", "caption", "location", "city__name")
    list_editable = ("is_published", "display_order")
    readonly_fields = ("hls_master_url", "hls_status", "processing_error", "duration", "created_at", "updated_at")
    fieldsets = (
        ("Shorts Video", {"fields": ("title", "headline", "caption", "location", "category", "state", "city", "frame_template", "video_file", "original_video", "thumbnail")}),
        ("HLS Processing", {"fields": ("hls_master_url", "hls_status", "processing_error", "duration")}),
        ("Status", {"fields": ("is_published", "display_order", "created_by")}),
        ("Counters", {"fields": ("views_count", "likes_count", "comments_count", "shares_count")}),
        ("Dates", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(ShortsComment)
class ShortsCommentAdmin(admin.ModelAdmin):
    list_display = ("short", "name", "created_at")
    search_fields = ("short__title", "name", "text")
    readonly_fields = ("created_at",)


@admin.register(ShortsLike)
class ShortsLikeAdmin(admin.ModelAdmin):
    list_display = ("short", "user", "created_at")
    search_fields = ("short__title", "user__username", "user__email")
    readonly_fields = ("created_at",)


@admin.register(ChannelFollow)
class ChannelFollowAdmin(admin.ModelAdmin):
    list_display = ("user", "channel_user", "created_at")
    search_fields = ("user__username", "user__email", "channel_user__username", "channel_user__email")
    readonly_fields = ("created_at",)


@admin.register(MobileAdminToken)
class MobileAdminTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "device_name", "created_at", "last_used_at")
    search_fields = ("user__username", "user__email", "device_name")
    readonly_fields = ("key", "created_at", "last_used_at")



@admin.register(MediaDownload)
class MediaDownloadAdmin(admin.ModelAdmin):
    list_display = ("title", "media_type", "status", "progress_percent", "created_by", "created_at")
    list_filter = ("status", "media_type")
    search_fields = ("title", "source_url")
    readonly_fields = ("progress_percent", "created_at", "updated_at", "error_message")
@admin.register(SocialRenderedVideo)
class SocialRenderedVideoAdmin(admin.ModelAdmin):
    list_display = ("title", "live_channel", "source_video", "frame_template", "render_format", "status", "progress_percent", "is_active", "is_downloadable", "created_at")
    list_filter = ("status", "render_format", "frame_category", "live_channel", "is_active", "is_downloadable", "created_at")
    search_fields = ("title", "headline", "ticker_label", "ticker_text", "frame_template", "broadcast_session_id", "render_key")
    readonly_fields = ("progress_percent", "render_key", "broadcast_session_id", "snapshot", "file_size", "resolution", "duration_seconds", "started_at", "completed_at", "created_at", "updated_at", "error_message")
    actions = ("retry_failed_render", "regenerate_thumbnail", "mark_active", "mark_inactive")

    @admin.action(description="Retry failed render")
    def retry_failed_render(self, request, queryset):
        from .tasks import render_live_broadcast_video_task

        count = 0
        for job in queryset.filter(status=SocialRenderedVideo.Status.FAILED):
            job.status = SocialRenderedVideo.Status.PENDING
            job.progress_percent = 0
            job.error_message = ""
            job.retry_count += 1
            job.save(update_fields=["status", "progress_percent", "error_message", "retry_count", "updated_at"])
            render_live_broadcast_video_task.delay(job.pk)
            count += 1
        self.message_user(request, f"{count} failed render jobs queued.")

    @admin.action(description="Regenerate thumbnail")
    def regenerate_thumbnail(self, request, queryset):
        from .views import generate_render_thumbnail

        count = 0
        for job in queryset.exclude(rendered_video=""):
            generate_render_thumbnail(job)
            job.save(update_fields=["thumbnail", "updated_at"])
            count += 1
        self.message_user(request, f"{count} thumbnails regenerated.")

    @admin.action(description="Mark selected active")
    def mark_active(self, request, queryset):
        self.message_user(request, f"{queryset.update(is_active=True)} rendered videos marked active.")

    @admin.action(description="Mark selected inactive")
    def mark_inactive(self, request, queryset):
        self.message_user(request, f"{queryset.update(is_active=False)} rendered videos marked inactive.")
