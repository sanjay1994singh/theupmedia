from pathlib import Path
import secrets
from urllib.parse import parse_qs, urlencode, urlparse

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.template.defaultfilters import slugify
from django.urls import reverse
from django.utils import timezone


class LiveTVCategory(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "name"]
        verbose_name = "Live TV Category"
        verbose_name_plural = "Live TV Categories"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)[:90] or "category"
            slug = base_slug
            counter = 2
            while LiveTVCategory.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)


class LiveTVState(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "name"]
        verbose_name = "Live TV State"
        verbose_name_plural = "Live TV States"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)[:90] or "state"
            slug = base_slug
            counter = 2
            while LiveTVState.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)


class LiveTVCity(models.Model):
    state = models.ForeignKey(LiveTVState, on_delete=models.CASCADE, related_name="cities")
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, blank=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["state__display_order", "state__name", "display_order", "name"]
        unique_together = ("state", "name")
        verbose_name = "Live TV City"
        verbose_name_plural = "Live TV Cities"

    def __str__(self):
        return f"{self.name}, {self.state.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)[:100] or "city"
            slug = base_slug
            counter = 2
            while LiveTVCity.objects.filter(state=self.state, slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)


class LiveTVChannel(models.Model):
    class SourceType(models.TextChoices):
        YOUTUBE = "youtube", "YouTube URL"
        DIRECT = "direct", "Direct Video Upload"
        HLS = "hls", "HLS / M3U8 Stream"
        PLAYLIST = "playlist", "Auto Live Playlist"

    class HLSStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    title = models.CharField(max_length=180)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    description = models.TextField(blank=True)
    source_type = models.CharField(max_length=20, choices=SourceType.choices, default=SourceType.YOUTUBE)
    youtube_url = models.URLField(blank=True, help_text="Paste YouTube watch, live, or embed URL.")
    stream_url = models.URLField(blank=True, help_text="For HLS/M3U8 or external MP4/WebM URLs.")
    video_file = models.FileField(upload_to="live-tv/videos/%Y/%m/", blank=True, null=True)
    hls_master_url = models.CharField(max_length=500, blank=True)
    hls_status = models.CharField(max_length=20, choices=HLSStatus.choices, default=HLSStatus.PENDING)
    hls_progress_percent = models.PositiveSmallIntegerField(default=0)
    processing_error = models.TextField(blank=True)
    duration = models.FloatField(blank=True, null=True)
    duration_seconds = models.PositiveIntegerField(default=0)
    auto_add_to_live = models.BooleanField(
        default=True,
        help_text="Automatically add this uploaded video to the main live playlist.",
    )
    auto_playlist_enabled = models.BooleanField(
        default=False,
        help_text="Use this record as the main synchronized auto live channel.",
    )
    loop_enabled = models.BooleanField(default=True)
    target_playlist_duration_seconds = models.PositiveIntegerField(
        default=10800,
        help_text="Target live playlist duration. 10800 seconds = 3 hours.",
    )
    playback_started_at = models.DateTimeField(blank=True, null=True)
    playlist_version = models.PositiveBigIntegerField(default=1)
    last_playlist_update = models.DateTimeField(blank=True, null=True)
    poster_image = models.ImageField(upload_to="live-tv/posters/%Y/%m/", blank=True, null=True)
    category = models.ForeignKey(LiveTVCategory, on_delete=models.SET_NULL, blank=True, null=True, related_name="channels")
    state = models.ForeignKey(LiveTVState, on_delete=models.SET_NULL, blank=True, null=True, related_name="channels")
    city = models.ForeignKey(LiveTVCity, on_delete=models.SET_NULL, blank=True, null=True, related_name="channels")
    is_active = models.BooleanField(default=True)
    is_live = models.BooleanField(default=True)
    lower_third_label = models.CharField(max_length=60, blank=True, default="")
    headline = models.CharField(max_length=180, blank=True, default="")
    reporter_label = models.CharField(max_length=60, blank=True, default="REPORTER")
    reporter_name = models.CharField(max_length=120, blank=True, default="")
    headline_change_seconds = models.PositiveSmallIntegerField(
        default=2,
        validators=[MinValueValidator(1), MaxValueValidator(60)],
        help_text="Seconds before the next headline appears.",
    )
    repeat_headlines = models.BooleanField(
        default=True,
        help_text="Repeat this video's headline sequence until the video ends.",
    )
    ticker_label = models.CharField(max_length=60, default="TODAY'S NEWS")
    ticker_text = models.TextField(default="Latest updates from The Up Media")

    meta_title = models.CharField(max_length=160, blank=True)
    meta_description = models.CharField(max_length=220, blank=True)
    display_order = models.PositiveIntegerField(default=0)
    push_notification_sent_at = models.DateTimeField(blank=True, null=True, editable=False)
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

    def clean(self):
        errors = {}
        if self.source_type != self.SourceType.PLAYLIST:
            if not self.category_id:
                errors["category"] = "Category is required."
            if not self.state_id:
                errors["state"] = "State is required."
            if not self.city_id:
                errors["city"] = "City is required."
        if self.city_id and self.state_id and self.city and self.city.state_id != self.state_id:
            errors["city"] = "City must belong to selected state."
        if self.auto_playlist_enabled and self.source_type != self.SourceType.PLAYLIST:
            errors["source_type"] = "Main auto playlist channel must use Auto Live Playlist source."
        if errors:
            raise ValidationError(errors)

    def delete(self, *args, **kwargs):
        files = {
            "video_file": self.video_file,
            "poster_image": self.poster_image,
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
        if (
            self.source_type == self.SourceType.PLAYLIST
            and self.auto_playlist_enabled
            and self.playlist_items.filter(is_active=True).exists()
        ):
            return self.SourceType.PLAYLIST
        if self.source_type == self.SourceType.YOUTUBE and self.youtube_embed_url:
            return self.SourceType.YOUTUBE
        if self.source_type == self.SourceType.DIRECT and self.video_file:
            return self.SourceType.DIRECT
        if self.source_type == self.SourceType.HLS and (self.hls_master_url or self.stream_url):
            return self.SourceType.HLS
        if self.video_file:
            return self.SourceType.DIRECT
        if self.hls_master_url or self.stream_url:
            return self.SourceType.HLS
        if self.youtube_embed_url:
            return self.SourceType.YOUTUBE
        return ""

    @property
    def hls_media_url(self):
        if not self.hls_master_url:
            return ""
        url = str(self.hls_master_url).strip()
        if url.startswith(("http://", "https://", "/")):
            return url
        media_url = settings.MEDIA_URL or "/media/"
        if not media_url.endswith("/"):
            media_url = f"{media_url}/"
        return f"{media_url}{url.lstrip('/')}"

    @property
    def effective_duration_seconds(self):
        try:
            value = int(self.duration_seconds or 0)
            if value > 0:
                return value
            fallback = int(float(self.duration or 0))
            return fallback if fallback > 0 else 0
        except (TypeError, ValueError, OverflowError):
            return 0

    @property
    def playlist_duration_seconds(self):
        return sum(
            max(0, int(value or 0))
            for value in self.playlist_items.filter(is_active=True).values_list("duration_seconds", flat=True)
        )

    @property
    def playlist_duration_minutes(self):
        return round(self.playlist_duration_seconds / 60, 2)

    @property
    def playlist_target_reached(self):
        return self.playlist_duration_seconds >= self.target_playlist_duration_seconds

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
        return f"https://www.youtube-nocookie.com/embed/{video_id}?{urlencode(params)}"

    @property
    def has_headline_content(self):
        return bool((self.headline or "").strip()) or self.rotating_headlines.filter(is_active=True).exists()


class LiveTVVideoHeadline(models.Model):
    video = models.ForeignKey(LiveTVChannel, on_delete=models.CASCADE, related_name="rotating_headlines")
    text = models.CharField(max_length=240)
    position = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "pk"]

    def __str__(self):
        return f"{self.video}: {self.text[:60]}"


class LiveTVPlaylistItem(models.Model):
    class Priority(models.TextChoices):
        NORMAL = "normal", "Add to End"
        NEXT = "next", "Play Next"
        IMMEDIATE = "immediate", "Play Immediately"

    channel = models.ForeignKey(LiveTVChannel, on_delete=models.CASCADE, related_name="playlist_items")
    video = models.ForeignKey(LiveTVChannel, on_delete=models.PROTECT, related_name="included_in_playlists")
    position = models.PositiveIntegerField(default=0)
    duration_seconds = models.PositiveIntegerField(default=0)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.NORMAL)
    is_active = models.BooleanField(default=True)
    added_at = models.DateTimeField(auto_now_add=True)
    removed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "pk"]
        indexes = [models.Index(fields=["channel", "is_active", "position"], name="live_playlist_order_idx")]
        constraints = [
            models.UniqueConstraint(fields=["channel", "video"], name="unique_live_playlist_video"),
            models.CheckConstraint(condition=~Q(channel=models.F("video")), name="live_playlist_no_self_ref"),
        ]

    def __str__(self):
        return f"{self.channel}: {self.position + 1}. {self.video}"

    def clean(self):
        errors = {}
        if self.channel_id and self.video_id and self.channel_id == self.video_id:
            errors["video"] = "Main channel cannot reference itself."
        if self.video_id:
            if self.video.source_type != LiveTVChannel.SourceType.DIRECT or not self.video.video_file:
                errors["video"] = "Only a direct uploaded video can be added to the live playlist."
            elif not self.video.is_active:
                errors["video"] = "Inactive video cannot be added to the live playlist."
            elif self.video.effective_duration_seconds <= 0:
                errors["duration_seconds"] = "A positive video duration is required."
        if errors:
            raise ValidationError(errors)


class LiveTVPlaylistCycle(models.Model):
    channel = models.ForeignKey(LiveTVChannel, on_delete=models.CASCADE, related_name="playlist_cycles")
    version = models.PositiveBigIntegerField()
    starts_at = models.DateTimeField()
    total_duration_seconds = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-starts_at", "-version"]
        constraints = [models.UniqueConstraint(fields=["channel", "version"], name="unique_live_playlist_cycle_version")]
        indexes = [models.Index(fields=["channel", "starts_at"], name="live_cycle_start_idx")]

    def __str__(self):
        return f"{self.channel} v{self.version}"


class LiveTVPlaylistCycleItem(models.Model):
    cycle = models.ForeignKey(LiveTVPlaylistCycle, on_delete=models.CASCADE, related_name="items")
    playlist_item = models.ForeignKey(LiveTVPlaylistItem, on_delete=models.CASCADE, related_name="cycle_items")
    video = models.ForeignKey(LiveTVChannel, on_delete=models.PROTECT, related_name="playlist_cycle_entries")
    position = models.PositiveIntegerField(default=0)
    duration_seconds = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "pk"]
        constraints = [models.UniqueConstraint(fields=["cycle", "position"], name="unique_live_cycle_position")]
        indexes = [models.Index(fields=["cycle", "position"], name="live_cycle_item_order_idx")]

    def __str__(self):
        return f"{self.cycle} item {self.position + 1}"


class AppMenu(models.Model):
    title = models.CharField(max_length=80)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    target_type = models.CharField(max_length=40, default="section", help_text="section, live_tv, shorts, videos, district, url")
    target_value = models.CharField(max_length=180, blank=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "title"]
        verbose_name = "App Menu"
        verbose_name_plural = "App Menus"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)[:90] or "menu"
            slug = base_slug
            counter = 2
            while AppMenu.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)


class HomeContent(models.Model):
    class Section(models.TextChoices):
        FEATURED = "featured", "Mukhya Khabrein"
        TOP_VIDEO = "top_video", "Top Video"

    class StreamType(models.TextChoices):
        DIRECT = "direct", "Direct MP4"
        HLS = "hls", "HLS / M3U8"
        YOUTUBE = "youtube", "YouTube"
        ACTION = "action", "App Action"

    section = models.CharField(max_length=20, choices=Section.choices, default=Section.FEATURED)
    title = models.CharField(max_length=160)
    subtitle = models.CharField(max_length=220, blank=True)
    badge_text = models.CharField(max_length=40, blank=True)
    thumbnail = models.ImageField(upload_to="live-tv/home/%Y/%m/", blank=True, null=True)
    image_url = models.URLField(blank=True)
    video_url = models.URLField(blank=True)
    youtube_url = models.URLField(blank=True)
    stream_type = models.CharField(max_length=20, choices=StreamType.choices, default=StreamType.DIRECT)
    duration = models.CharField(max_length=24, blank=True)
    viewers_count = models.PositiveIntegerField(default=0)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["section", "display_order", "-created_at"]
        verbose_name = "Home Content"
        verbose_name_plural = "Home Contents"

    def __str__(self):
        return f"{self.get_section_display()}: {self.title}"

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
        return f"https://www.youtube-nocookie.com/embed/{video_id}?{urlencode(params)}"


class HomeUtility(models.Model):
    title = models.CharField(max_length=80)
    subtitle = models.CharField(max_length=160, blank=True)
    icon = models.CharField(max_length=40, default="play-circle")
    action = models.CharField(max_length=80, default="live_tv")
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "title"]
        verbose_name = "Home Utility"
        verbose_name_plural = "Home Utilities"

    def __str__(self):
        return self.title


class LiveTVSetting(models.Model):
    name = models.CharField(max_length=120, default="The Up Media Live TV")
    live_label = models.CharField(max_length=40, default="LIVE")
    channel_logo = models.ImageField(upload_to="live-tv/settings/", blank=True, null=True)
    show_channel_logo = models.BooleanField(default=True)
    show_lower_third = models.BooleanField(default=True)
    show_ticker = models.BooleanField(default=True)
    autoplay = models.BooleanField(default=False)
    show_live_badge = models.BooleanField(default=True)
    web_live_badge_size_percent = models.PositiveSmallIntegerField(
        default=100,
        help_text="Web Live badge size in percent (40-200).",
        validators=[MinValueValidator(40), MaxValueValidator(200)],
    )
    mobile_live_badge_size_percent = models.PositiveSmallIntegerField(
        default=100,
        help_text="Mobile app Live badge size in percent (40-200).",
        validators=[MinValueValidator(40), MaxValueValidator(200)],
    )
    default_lower_third_label = models.CharField(max_length=60, null=True,blank=True)
    default_headline = models.CharField(max_length=180, null=True,blank=True)
    default_ticker_label = models.CharField(max_length=60, null=True,blank=True)
    default_ticker_text = models.TextField(null=True, blank=True)
    ticker_speed_seconds = models.PositiveSmallIntegerField(default=22)
    mobile_ticker_speed_seconds = models.PositiveSmallIntegerField(default=12)
    ticker_started_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Live TV Setting"
        verbose_name_plural = "Live TV Settings"

    def __str__(self):
        return self.name

    @property
    def web_live_badge_scale(self):
        return f"{max(40, min(200, self.web_live_badge_size_percent)) / 100:.2f}"

    @classmethod
    def get_solo(cls):
        setting, _created = cls.objects.get_or_create(pk=1, defaults={"name": "The Up Media Live TV"})
        return setting

    def save(self, *args, **kwargs):
        self.pk = 1
        ticker_fields = (
            "default_ticker_label",
            "default_ticker_text",
            "ticker_speed_seconds",
            "mobile_ticker_speed_seconds",
        )
        previous = type(self).objects.filter(pk=self.pk).values(*ticker_fields).first()
        if previous and any(previous[field] != getattr(self, field) for field in ticker_fields):
            self.ticker_started_at = timezone.now()
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {"ticker_started_at"}
        super().save(*args, **kwargs)

class NewsTickerSetting(models.Model):
    label = models.CharField(max_length=60, default="ताज़ा खबर")
    text = models.TextField(default="Latest updates from The Up Media")
    speed_seconds = models.PositiveSmallIntegerField(default=22)
    mobile_speed_seconds = models.PositiveSmallIntegerField(default=12)
    style = models.CharField(max_length=60, default="red_white_slant")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "News Ticker Setting"
        verbose_name_plural = "News Ticker Settings"

    def __str__(self):
        return self.label

    @classmethod
    def get_solo(cls):
        ticker, _created = cls.objects.get_or_create(pk=1)
        return ticker

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)


class ShortsVideo(models.Model):
    class HLSStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    title = models.CharField(max_length=180, blank=True)
    headline = models.CharField(max_length=180, blank=True)
    caption = models.TextField(blank=True)
    location = models.CharField(max_length=120, blank=True)
    category = models.ForeignKey(LiveTVCategory, on_delete=models.SET_NULL, blank=True, null=True, related_name="shorts")
    state = models.ForeignKey(LiveTVState, on_delete=models.SET_NULL, blank=True, null=True, related_name="shorts")
    city = models.ForeignKey(LiveTVCity, on_delete=models.SET_NULL, blank=True, null=True, related_name="shorts")
    frame_template = models.CharField(max_length=60, default="normal_black_red")
    video_file = models.FileField(upload_to="shorts/videos/%Y/%m/")
    original_video = models.FileField(upload_to="shorts/original/%Y/%m/", blank=True, null=True)
    hls_master_url = models.CharField(max_length=500, blank=True)
    hls_status = models.CharField(max_length=20, choices=HLSStatus.choices, default=HLSStatus.PENDING)
    hls_progress_percent = models.PositiveSmallIntegerField(default=0)
    processing_error = models.TextField(blank=True)
    duration = models.FloatField(blank=True, null=True)
    thumbnail = models.ImageField(upload_to="shorts/thumbnails/%Y/%m/", blank=True, null=True)
    is_published = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)
    likes_count = models.PositiveIntegerField(default=0)
    comments_count = models.PositiveIntegerField(default=0)
    shares_count = models.PositiveIntegerField(default=0)
    views_count = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="live_tv_shorts")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "-created_at"]
        indexes = [
            models.Index(fields=["is_published", "display_order"], name="shorts_published_order_idx"),
        ]

    def __str__(self):
        return self.title or Path(self.video_file.name).stem or "Shorts video"

    def save(self, *args, **kwargs):
        if not self.title:
            self.title = Path(self.video_file.name).stem[:180] if self.video_file else "The UP Media Shorts"
        super().save(*args, **kwargs)

    def clean(self):
        errors = {}
        if not self.category_id:
            errors["category"] = "Category is required."
        if not self.state_id:
            errors["state"] = "State is required."
        if not self.city_id:
            errors["city"] = "City is required."
        elif self.state_id and self.city and self.city.state_id != self.state_id:
            errors["city"] = "City must belong to selected state."
        if errors:
            raise ValidationError(errors)

    def delete(self, *args, **kwargs):
        files = [self.video_file, self.thumbnail]
        result = super().delete(*args, **kwargs)
        for file_obj in files:
            if file_obj and file_obj.name:
                file_obj.delete(save=False)
        return result


class ShortsComment(models.Model):
    short = models.ForeignKey(ShortsVideo, on_delete=models.CASCADE, related_name="comments")
    name = models.CharField(max_length=80, blank=True)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["short", "-created_at"], name="short_comment_recent_idx"),
        ]

    def __str__(self):
        return f"{self.name or 'Viewer'}: {self.text[:40]}"


class ShortsLike(models.Model):
    short = models.ForeignKey(ShortsVideo, on_delete=models.CASCADE, related_name="short_likes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="liked_live_tv_shorts")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["short", "user"], name="unique_shorts_like_user"),
        ]
        indexes = [
            models.Index(fields=["short", "user"], name="shorts_like_short_user_idx"),
        ]

    def __str__(self):
        return f"{self.user} liked {self.short_id}"


class ChannelFollow(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="live_tv_following")
    channel_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="live_tv_followers")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "channel_user"], name="unique_live_tv_channel_follow"),
        ]
        indexes = [
            models.Index(fields=["channel_user", "user"], name="channel_follow_user_idx"),
        ]

    def __str__(self):
        return f"{self.user} follows {self.channel_user}"


class MobileAdminToken(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="live_tv_mobile_tokens")
    key = models.CharField(max_length=64, unique=True, db_index=True)
    device_name = models.CharField(max_length=160, blank=True)
    last_used_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} mobile admin token"

    @classmethod
    def create_for_user(cls, user, device_name=""):
        clean_device_name = device_name[:160]
        token = cls.objects.create(
            user=user,
            key=secrets.token_urlsafe(40),
            device_name=clean_device_name,
        )
        cls.objects.filter(user=user).exclude(pk=token.pk).delete()
        return token


class PushDevice(models.Model):
    token = models.CharField(max_length=255, unique=True, db_index=True)
    platform = models.CharField(max_length=20, blank=True)
    device_name = models.CharField(max_length=160, blank=True)
    is_active = models.BooleanField(default=True)
    last_registered_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-last_registered_at"]

    def __str__(self):
        return f"{self.platform or 'mobile'} push device"



class FacebookLiveSetting(models.Model):
    class Status(models.TextChoices):
        STOPPED = "stopped", "Stopped"
        STARTING = "starting", "Starting"
        LIVE = "live", "Live"
        FAILED = "failed", "Failed"

    name = models.CharField(max_length=120, default="Facebook Live")
    server_url = models.CharField(max_length=500, default="rtmps://live-api-s.facebook.com:443/rtmp/")
    stream_key = models.CharField(max_length=500, blank=True)
    is_enabled = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.STOPPED)
    process_id = models.PositiveIntegerField(blank=True, null=True)
    last_error = models.TextField(blank=True)
    log_file = models.CharField(max_length=500, blank=True)
    started_at = models.DateTimeField(blank=True, null=True)
    stopped_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Facebook Live Setting"
        verbose_name_plural = "Facebook Live Settings"

    def __str__(self):
        return self.name

    @classmethod
    def get_solo(cls):
        setting, _created = cls.objects.get_or_create(pk=1, defaults={"name": "Facebook Live"})
        return setting

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

class MediaDownload(models.Model):
    class Status(models.TextChoices):
        PROCESSING = "processing", "Processing"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    class MediaType(models.TextChoices):
        VIDEO = "video", "Video"
        AUDIO = "audio", "Audio"
        UNKNOWN = "unknown", "Unknown"

    title = models.CharField(max_length=180)
    source_url = models.URLField(max_length=1200)
    media_type = models.CharField(max_length=20, choices=MediaType.choices, default=MediaType.UNKNOWN)
    downloaded_file = models.FileField(upload_to="media-downloads/%Y/%m/", blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PROCESSING)
    progress_percent = models.PositiveSmallIntegerField(default=0)
    error_message = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="live_tv_media_downloads")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class SocialRenderedVideo(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    title = models.CharField(max_length=180)
    headline = models.CharField(max_length=180, blank=True)
    ticker_label = models.CharField(max_length=60, default="BREAKING NEWS")
    ticker_text = models.TextField(blank=True)
    lower_third_label = models.CharField(max_length=60, default="BREAKING NEWS")
    render_format = models.CharField(max_length=10, default="16:9", db_default="16:9")
    frame_category = models.CharField(max_length=40, blank=True)
    frame_template = models.CharField(max_length=60, blank=True)
    source_video = models.ForeignKey(
        LiveTVChannel,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="broadcast_rendered_videos",
    )
    live_channel = models.ForeignKey(
        LiveTVChannel,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="live_broadcast_renders",
    )
    playlist_item = models.ForeignKey(
        LiveTVPlaylistItem,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="rendered_broadcasts",
    )
    broadcast_session_id = models.CharField(max_length=120, blank=True)
    render_key = models.CharField(max_length=180, blank=True, unique=True, null=True)
    snapshot = models.JSONField(default=dict, blank=True)
    original_video = models.FileField(upload_to="social-render/original/%Y/%m/", blank=True, null=True)
    rendered_video = models.FileField(upload_to="social-render/rendered/%Y/%m/", blank=True, null=True)
    thumbnail = models.ImageField(upload_to="social-render/thumbnails/%Y/%m/", blank=True, null=True)
    duration_seconds = models.PositiveIntegerField(default=0)
    file_size = models.PositiveBigIntegerField(default=0)
    resolution = models.CharField(max_length=40, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PROCESSING)
    progress_percent = models.PositiveSmallIntegerField(default=0)
    error_message = models.TextField(blank=True)
    retry_count = models.PositiveSmallIntegerField(default=0)
    started_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_downloadable = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="social_rendered_videos")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"], name="rendered_status_created_idx"),
            models.Index(fields=["live_channel", "broadcast_session_id"], name="rendered_session_idx"),
        ]

    def __str__(self):
        return self.title

    @property
    def progress_percentage(self):
        return self.progress_percent

    @property
    def is_completed(self):
        return self.status in {self.Status.COMPLETED, self.Status.DONE}
