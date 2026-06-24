from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

from django.conf import settings
from django.db import models
from django.template.defaultfilters import slugify
from django.urls import reverse


class LiveTVChannel(models.Model):
    class SourceType(models.TextChoices):
        YOUTUBE = "youtube", "YouTube URL"
        DIRECT = "direct", "Direct Video Upload"
        HLS = "hls", "HLS / M3U8 Stream"

    title = models.CharField(max_length=180)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    description = models.TextField(blank=True)
    source_type = models.CharField(max_length=20, choices=SourceType.choices, default=SourceType.YOUTUBE)
    youtube_url = models.URLField(blank=True, help_text="Paste YouTube watch, live, or embed URL.")
    stream_url = models.URLField(blank=True, help_text="For HLS/M3U8 or external MP4/WebM URLs.")
    video_file = models.FileField(upload_to="live-tv/videos/%Y/%m/", blank=True, null=True)
    poster_image = models.ImageField(upload_to="live-tv/posters/%Y/%m/", blank=True, null=True)
    channel_logo = models.ImageField(upload_to="live-tv/logos/", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_live = models.BooleanField(default=True)
    autoplay = models.BooleanField(default=False)

    show_lower_third = models.BooleanField(default=True)
    lower_third_label = models.CharField(max_length=60, default="BREAKING NEWS")
    headline = models.CharField(max_length=180, default="The Up Media Live TV")
    show_ticker = models.BooleanField(default=True)
    ticker_label = models.CharField(max_length=60, default="TODAY'S NEWS")
    ticker_text = models.CharField(max_length=260, default="Latest updates from The Up Media")
    show_channel_logo = models.BooleanField(default=True)

    meta_title = models.CharField(max_length=160, blank=True)
    meta_description = models.CharField(max_length=220, blank=True)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "title"]
        indexes = [
            models.Index(fields=["is_active", "display_order"], name="live_tv_active_order_idx"),
            models.Index(fields=["slug"], name="live_tv_slug_idx"),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        old_files = {}
        if self.pk:
            old_channel = LiveTVChannel.objects.filter(pk=self.pk).first()
            if old_channel:
                old_files = {
                    "video_file": old_channel.video_file,
                    "poster_image": old_channel.poster_image,
                    "channel_logo": old_channel.channel_logo,
                }

        if not self.slug:
            base_slug = slugify(self.title)[:180] or "live-tv"
            slug = base_slug
            counter = 2
            while LiveTVChannel.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        if not self.meta_title:
            self.meta_title = self.title[:160]
        if not self.meta_description:
            self.meta_description = (self.description or self.headline)[:220]
        super().save(*args, **kwargs)
        for field_name, old_file in old_files.items():
            new_file = getattr(self, field_name)
            if old_file and old_file.name and old_file.name != getattr(new_file, "name", ""):
                self._delete_file_if_unused(field_name, old_file)

    def delete(self, *args, **kwargs):
        files = {
            "video_file": self.video_file,
            "poster_image": self.poster_image,
            "channel_logo": self.channel_logo,
        }
        result = super().delete(*args, **kwargs)
        for field_name, file_obj in files.items():
            self._delete_file_if_unused(field_name, file_obj)
        return result

    def _delete_file_if_unused(self, field_name, file_obj):
        if not file_obj or not file_obj.name:
            return
        is_used = LiveTVChannel.objects.filter(**{field_name: file_obj.name}).exists()
        if not is_used:
            file_obj.delete(save=False)

    def get_absolute_url(self):
        return reverse("live_tv:detail", kwargs={"slug": self.slug})

    @property
    def player_source_type(self):
        if self.source_type == self.SourceType.YOUTUBE and self.youtube_embed_url:
            return self.SourceType.YOUTUBE
        if self.source_type == self.SourceType.DIRECT and self.video_file:
            return self.SourceType.DIRECT
        if self.source_type == self.SourceType.HLS and self.stream_url:
            return self.SourceType.HLS
        if self.video_file:
            return self.SourceType.DIRECT
        if self.stream_url:
            return self.SourceType.HLS
        if self.youtube_embed_url:
            return self.SourceType.YOUTUBE
        return ""

    @property
    def video_mime_type(self):
        if not self.video_file:
            return "video/mp4"
        suffix = Path(self.video_file.name).suffix.lower()
        if suffix == ".webm":
            return "video/webm"
        if suffix in {".m3u8", ".m3u"}:
            return "application/x-mpegURL"
        return "video/mp4"

    @property
    def youtube_embed_url(self):
        if not self.youtube_url:
            return ""
        parsed = urlparse(self.youtube_url)
        host = parsed.netloc.lower()
        video_id = ""

        if "youtu.be" in host:
            video_id = parsed.path.strip("/").split("/")[0]
        elif "youtube.com" in host:
            if parsed.path.startswith("/embed/"):
                video_id = parsed.path.split("/embed/", 1)[1].split("/")[0]
            elif parsed.path.startswith("/live/"):
                video_id = parsed.path.split("/live/", 1)[1].split("/")[0]
            elif parsed.path.startswith("/shorts/"):
                video_id = parsed.path.split("/shorts/", 1)[1].split("/")[0]
            else:
                video_id = parse_qs(parsed.query).get("v", [""])[0]

        if not video_id:
            return self.youtube_url

        params = {
            "rel": "0",
            "modestbranding": "1",
            "playsinline": "1",
            "enablejsapi": "1",
            "origin": settings.SITE_DOMAIN,
        }
        if self.autoplay:
            params.update({"autoplay": "1", "mute": "1"})
        return f"https://www.youtube-nocookie.com/embed/{video_id}?{urlencode(params)}"
