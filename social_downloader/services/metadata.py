from urllib.parse import urlparse

from django.conf import settings
from django.core.exceptions import ValidationError

from .validators import validate_public_media_url


def import_ytdlp():
    try:
        from yt_dlp import YoutubeDL
        from yt_dlp.utils import DownloadError
    except ImportError as exc:
        raise RuntimeError("yt-dlp is not installed. Install it with: pip install -U yt-dlp") from exc
    return YoutubeDL, DownloadError


def human_duration(seconds):
    if not seconds:
        return ""
    seconds = int(seconds)
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{sec:02d}"
    return f"{minutes}:{sec:02d}"


def compact_formats(formats):
    seen = set()
    rows = []
    for item in formats or []:
        height = item.get("height")
        ext = item.get("ext") or ""
        filesize = item.get("filesize") or item.get("filesize_approx")
        acodec = item.get("acodec")
        vcodec = item.get("vcodec")
        if height:
            label = f"{height}p"
        elif vcodec == "none" and acodec != "none":
            label = f"Audio {ext}".strip()
        else:
            continue
        key = (label, ext)
        if key in seen:
            continue
        seen.add(key)
        rows.append({"label": label, "ext": ext, "filesize": filesize})
    return rows[:30]


def extract_metadata(url):
    validate_public_media_url(url)
    YoutubeDL, DownloadError = import_ytdlp()
    max_duration = int(getattr(settings, "SOCIAL_DOWNLOADER_MAX_DURATION_SECONDS", 1800))
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "extract_flat": False,
        "socket_timeout": 20,
    }
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except DownloadError as exc:
        raise ValidationError("This URL is not supported or the media is not public.") from exc

    if info.get("_type") == "playlist":
        raise ValidationError("Playlist bulk download is not supported. Please paste a single video URL.")
    duration = info.get("duration")
    if duration and duration > max_duration:
        raise ValidationError(f"Video is too long. Maximum allowed duration is {max_duration // 60} minutes.")

    parsed = urlparse(info.get("webpage_url") or url)
    return {
        "source_url": info.get("webpage_url") or url,
        "source_domain": parsed.netloc.lower(),
        "extractor_name": info.get("extractor_key") or info.get("extractor") or "",
        "title": info.get("title") or "Untitled media",
        "thumbnail_url": info.get("thumbnail") or "",
        "duration_seconds": duration,
        "duration_label": human_duration(duration),
        "uploader": info.get("uploader") or info.get("channel") or "",
        "formats": compact_formats(info.get("formats")),
    }
