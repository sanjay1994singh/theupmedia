from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import SocialMediaDownload


@admin.register(SocialMediaDownload)
class SocialMediaDownloadAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "download_type",
        "status",
        "progress_percent",
        "file_size",
        "user",
        "created_at",
        "file_link",
    )
    list_filter = ("status", "download_type", "extractor_name", "created_at")
    search_fields = ("title", "source_url", "source_domain", "user__username", "user__email")
    readonly_fields = (
        "progress_percent",
        "downloaded_bytes",
        "total_bytes",
        "relative_file_path",
        "file_size",
        "started_at",
        "completed_at",
        "created_at",
        "updated_at",
        "file_link",
    )
    date_hierarchy = "created_at"

    def file_link(self, obj):
        if not obj.relative_file_path or obj.status != SocialMediaDownload.Status.COMPLETED:
            return "-"
        return format_html('<a href="{}" target="_blank">Download</a>', reverse("social_downloader:file", kwargs={"pk": obj.pk}))

    file_link.short_description = "File"

