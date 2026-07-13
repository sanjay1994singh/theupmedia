from django.conf import settings
from django.db import models
from django.urls import reverse


class SocialMediaDownload(models.Model):
    class DownloadType(models.TextChoices):
        VIDEO = "video", "Video"
        AUDIO = "audio", "Audio"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        EXPIRED = "expired", "Expired"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="social_downloads",
        null=True,
        blank=True,
    )
    source_url = models.URLField(max_length=2000)
    source_domain = models.CharField(max_length=255, blank=True)
    extractor_name = models.CharField(max_length=100, blank=True)
    title = models.CharField(max_length=500, blank=True)
    thumbnail_url = models.URLField(max_length=2000, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    download_type = models.CharField(max_length=10, choices=DownloadType.choices)
    selected_format = models.CharField(max_length=100, blank=True)
    selected_quality = models.CharField(max_length=50, blank=True)
    audio_format = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    progress_percent = models.PositiveSmallIntegerField(default=0)
    downloaded_bytes = models.BigIntegerField(default=0)
    total_bytes = models.BigIntegerField(null=True, blank=True)
    relative_file_path = models.CharField(max_length=1000, blank=True)
    original_filename = models.CharField(max_length=500, blank=True)
    stored_filename = models.CharField(max_length=500, blank=True)
    file_extension = models.CharField(max_length=20, blank=True)
    file_size = models.BigIntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="socdl_user_created_idx"),
            models.Index(fields=["status", "-created_at"], name="socdl_status_created_idx"),
        ]

    def __str__(self):
        return self.title or self.source_url

    def get_file_url(self):
        if self.status != self.Status.COMPLETED or not self.relative_file_path:
            return ""
        return reverse("social_downloader:file", kwargs={"pk": self.pk})
