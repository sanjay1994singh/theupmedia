import ipaddress
import os
import socket
import re
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import uuid4

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate
from django.core.files import File
from django.core.files.base import ContentFile
from django.db import close_old_connections
from django.db.models import Q
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_POST

from .forms import LiveTVChannelForm
from .models import FacebookLiveSetting, LiveTVChannel, LiveTVSetting, MediaDownload, MobileAdminToken, MobileVideoUpload, SocialRenderedVideo
from news.models import Article

RESTRICTED_DOWNLOAD_HOSTS = {
    "youtube.com",
    "youtu.be",
    "facebook.com",
    "fb.watch",
    "instagram.com",
    "x.com",
    "twitter.com",
}
ALLOWED_DOWNLOAD_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".m4v",
    ".webm",
    ".mkv",
    ".mp3",
    ".m4a",
    ".aac",
    ".wav",
    ".ogg",
}



def enqueue_media_download_job(job_id):
    if getattr(settings, "LIVE_TV_RENDER_USE_CELERY", True):
        try:
            from .tasks import download_media_task

            download_media_task.delay(job_id)
            return "celery"
        except Exception as exc:
            MediaDownload.objects.filter(pk=job_id).update(
                error_message=f"Celery enqueue failed, fallback thread started: {exc}",
            )

    import threading

    threading.Thread(target=run_media_download_job, args=(job_id,), daemon=True).start()
    return "thread"

def enqueue_social_render_job(job_id):
    if getattr(settings, "LIVE_TV_RENDER_USE_CELERY", True):
        try:
            from .tasks import render_social_video_task

            render_social_video_task.delay(job_id)
            return "celery"
        except Exception as exc:
            SocialRenderedVideo.objects.filter(pk=job_id).update(
                error_message=f"Celery enqueue failed, fallback thread started: {exc}",
            )

    import threading

    threading.Thread(target=run_social_render_job, args=(job_id,), daemon=True).start()
    return "thread"


def next_live_tv_channel(active_channel, channels):
    channels = list(channels)
    if not active_channel or not channels:
        return None
    for index, channel in enumerate(channels):
        if channel.pk == active_channel.pk:
            return channels[(index + 1) % len(channels)]
    return channels[0]


def live_tv_context(active_channel, channels, force_autoplay=False):
    channels = list(channels)
    next_channel = next_live_tv_channel(active_channel, channels)
    latest_news = Article.published.select_related("category", "state", "city")[:6]
    return {
        "active_channel": active_channel,
        "channels": channels,
        "next_channel": next_channel,
        "loop_same_channel": bool(active_channel and next_channel and active_channel.pk == next_channel.pk),
        "force_autoplay": force_autoplay,
        "latest_news": latest_news,
        "live_settings": live_tv_setting(),
    }


def absolute_media_url(request, file_obj):
    if not file_obj:
        return ""
    return request.build_absolute_uri(file_obj.url)




def facebook_live_setting():
    return FacebookLiveSetting.get_solo()


def mask_secret(value):
    if not value:
        return ""
    if len(value) <= 8:
        return "********"
    return f"{value[:4]}...{value[-4:]}"




def tail_file(path, max_chars=2500):
    if not path:
        return ""
    try:
        file_path = Path(path)
        if not file_path.exists():
            return ""
        text = file_path.read_text(encoding="utf-8", errors="replace")
        return text[-max_chars:].strip()
    except OSError:
        return ""

def process_is_running(pid):
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError):
        return False


def serialize_facebook_live_setting(setting):
    is_running = process_is_running(setting.process_id)
    status = FacebookLiveSetting.Status.LIVE if is_running and setting.status in {FacebookLiveSetting.Status.STARTING, FacebookLiveSetting.Status.LIVE} else setting.status
    if setting.process_id and not is_running and setting.status in {FacebookLiveSetting.Status.STARTING, FacebookLiveSetting.Status.LIVE}:
        setting.status = FacebookLiveSetting.Status.STOPPED
        setting.process_id = None
        setting.stopped_at = timezone.now()
        setting.save(update_fields=["status", "process_id", "stopped_at", "updated_at"])
        status = setting.status
    return {
        "id": setting.pk,
        "name": setting.name,
        "server_url": setting.server_url,
        "stream_key_set": bool(setting.stream_key),
        "stream_key_masked": mask_secret(setting.stream_key),
        "is_enabled": setting.is_enabled,
        "status": status,
        "process_id": setting.process_id if process_is_running(setting.process_id) else None,
        "last_error": setting.last_error,
        "log_tail": tail_file(setting.log_file),
        "started_at": setting.started_at.isoformat() if setting.started_at else "",
        "stopped_at": setting.stopped_at.isoformat() if setting.stopped_at else "",
        "updated_at": setting.updated_at.isoformat() if setting.updated_at else "",
    }


def active_live_tv_channel():
    channels = LiveTVChannel.objects.filter(is_active=True)
    return channels.filter(is_live=True).first() or channels.first()


def facebook_stream_target(setting):
    server_url = (setting.server_url or "").strip()
    stream_key = (setting.stream_key or "").strip()
    if not server_url or not stream_key:
        raise ValueError("Facebook server URL and stream key required.")
    if not server_url.endswith("/"):
        server_url = f"{server_url}/"
    return f"{server_url}{stream_key}"


def facebook_live_input_for_channel(channel):
    if not channel:
        raise ValueError("No active Live TV channel found.")
    if channel.player_source_type == LiveTVChannel.SourceType.DIRECT and channel.video_file:
        return str(Path(channel.video_file.path)), True
    if channel.player_source_type == LiveTVChannel.SourceType.HLS and channel.stream_url:
        return channel.stream_url, False
    raise ValueError("Facebook Live supports uploaded/direct video or HLS stream only. YouTube embed cannot be restreamed.")


def facebook_live_filter(channel):
    setting = live_tv_setting()
    label_text = channel.lower_third_label or setting.default_lower_third_label
    headline_text = channel.headline or setting.default_headline
    ticker_text = channel.ticker_text or setting.default_ticker_text
    title_text = channel.title or setting.name
    label_file = ffmpeg_text_file(label_text, "fb-label")
    headline_file = ffmpeg_text_file(headline_text, "fb-headline")
    ticker_file = ffmpeg_text_file("    |    ".join([ticker_text] * 4), "fb-ticker")
    title_file = ffmpeg_text_file(title_text, "fb-title")
    devanagari_font = ffmpeg_font_file()
    latin_font = ffmpeg_latin_font_file()
    label_font_arg = ffmpeg_font_arg_for_text(label_text, devanagari_font, latin_font)
    headline_font_arg = ffmpeg_font_arg_for_text(headline_text, devanagari_font, latin_font)
    ticker_font_arg = ffmpeg_font_arg_for_text(ticker_text, devanagari_font, latin_font)
    title_font_arg = ffmpeg_font_arg_for_text(title_text, devanagari_font, latin_font)
    return ",".join([
        "scale=1280:720:force_original_aspect_ratio=decrease",
        "pad=1280:720:(ow-iw)/2:(oh-ih)/2:black",
        "drawbox=x=22:y=24:w=98:h=44:color=#d71920@0.95:t=fill",
        f"drawtext=text='LIVE'{label_font_arg}:x=42:y=34:fontsize=24:fontcolor=white",
        "drawbox=x=0:y=560:w=1280:h=58:color=white@0.94:t=fill",
        "drawbox=x=0:y=560:w=200:h=58:color=#d71920@0.98:t=fill",
        f"drawtext=textfile='{ffmpeg_path(label_file)}'{label_font_arg}:x=24:y=576:fontsize=28:fontcolor=white",
        f"drawtext=textfile='{ffmpeg_path(headline_file)}'{headline_font_arg}:x=220:y=573:fontsize=30:fontcolor=#111827",
        "drawbox=x=0:y=618:w=1280:h=40:color=#f8d24c@0.98:t=fill",
        f"drawtext=textfile='{ffmpeg_path(ticker_file)}'{ticker_font_arg}:x=w-mod(t*160\\,w+tw):y=628:fontsize=22:fontcolor=#111827",
        "drawbox=x=0:y=658:w=1280:h=62:color=#08111f@0.96:t=fill",
        f"drawtext=textfile='{ffmpeg_path(title_file)}'{title_font_arg}:x=26:y=674:fontsize=28:fontcolor=white",
    ])


def start_facebook_live_process(setting):
    if process_is_running(setting.process_id):
        return setting
    channel = active_live_tv_channel()
    input_source, should_loop = facebook_live_input_for_channel(channel)
    command = [ffmpeg_binary(), "-hide_banner", "-loglevel", "info", "-stats", "-stats_period", "2", "-nostdin"]
    if should_loop:
        command.extend(["-stream_loop", "-1"])
    command.extend([
        "-re",
        "-i",
        input_source,
        "-vf",
        facebook_live_filter(channel),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-tune",
        "zerolatency",
        "-pix_fmt",
        "yuv420p",
        "-r",
        "30",
        "-g",
        "60",
        "-b:v",
        "2500k",
        "-maxrate",
        "2500k",
        "-bufsize",
        "5000k",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-ar",
        "44100",
        "-ac",
        "2",
        "-flvflags",
        "no_duration_filesize",
        "-f",
        "flv",
        facebook_stream_target(setting),
    ])
    log_dir = Path(settings.MEDIA_ROOT) / "facebook-live-logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"facebook-live-{uuid4().hex}.log"
    with log_path.open("w", encoding="utf-8", errors="replace") as log_file:
        process = subprocess.Popen(
            command,
            stdout=log_file,
            stderr=log_file,
            text=True,
            start_new_session=(os.name != "nt"),
        )
    time.sleep(5)
    if process.poll() is not None:
        error_text = tail_file(log_path) or "FFmpeg exited before Facebook accepted the stream."
        setting.status = FacebookLiveSetting.Status.FAILED
        setting.process_id = None
        setting.last_error = error_text
        setting.log_file = str(log_path)
        setting.stopped_at = timezone.now()
        setting.save(update_fields=["status", "process_id", "last_error", "log_file", "stopped_at", "updated_at"])
        raise RuntimeError(error_text)
    setting.status = FacebookLiveSetting.Status.LIVE
    setting.process_id = process.pid
    setting.last_error = ""
    setting.log_file = str(log_path)
    setting.started_at = timezone.now()
    setting.stopped_at = None
    setting.save(update_fields=["status", "process_id", "last_error", "log_file", "started_at", "stopped_at", "updated_at"])
    return setting


def stop_facebook_live_process(setting):
    pid = setting.process_id
    if pid and process_is_running(pid):
        try:
            if os.name != "nt":
                os.killpg(os.getpgid(int(pid)), signal.SIGTERM)
            else:
                os.kill(int(pid), signal.SIGTERM)
        except OSError as exc:
            setting.last_error = str(exc)
    setting.status = FacebookLiveSetting.Status.STOPPED
    setting.process_id = None
    setting.stopped_at = timezone.now()
    setting.save(update_fields=["status", "process_id", "last_error", "stopped_at", "updated_at"])
    return setting

def live_tv_setting():
    return LiveTVSetting.get_solo()


def serialize_live_tv_setting(request, setting):
    return {
        "id": setting.pk,
        "name": setting.name,
        "live_label": setting.live_label,
        "channel_logo": absolute_media_url(request, setting.channel_logo),
        "show_live_badge": setting.show_live_badge,
        "show_channel_logo": setting.show_channel_logo,
        "show_lower_third": setting.show_lower_third,
        "show_ticker": setting.show_ticker,
        "autoplay": setting.autoplay,
        "default_lower_third_label": setting.default_lower_third_label,
        "default_headline": setting.default_headline,
        "default_ticker_label": setting.default_ticker_label,
        "default_ticker_text": setting.default_ticker_text,
        "ticker_speed_seconds": setting.ticker_speed_seconds,
        "mobile_ticker_speed_seconds": setting.mobile_ticker_speed_seconds,
        "updated_at": setting.updated_at.isoformat(),
    }

def ticker_items(channel):
    if not channel or not channel.ticker_text:
        return []
    raw_items = channel.ticker_text.replace("\r", "\n").replace("|", "\n").split("\n")
    return [item.strip() for item in raw_items if item.strip()]


def serialize_channel_for_mobile(request, channel):
    setting = live_tv_setting()
    player_type = channel.player_source_type
    stream_url = ""
    youtube_embed_url = ""

    if player_type == LiveTVChannel.SourceType.DIRECT:
        stream_url = absolute_media_url(request, channel.video_file)
    elif player_type == LiveTVChannel.SourceType.HLS:
        stream_url = channel.stream_url
    elif player_type == LiveTVChannel.SourceType.YOUTUBE:
        youtube_embed_url = channel.youtube_embed_url

    ticker = ticker_items(channel)
    if not ticker:
        ticker = ticker_items(type("DefaultTicker", (), {"ticker_text": setting.default_ticker_text})())

    return {
        "id": channel.pk,
        "title": channel.title,
        "description": channel.description,
        "headline": channel.headline or setting.default_headline,
        "lower_third_label": channel.lower_third_label or setting.default_lower_third_label,
        "ticker_label": channel.ticker_label or setting.default_ticker_label,
        "ticker": ticker,
        "player_type": player_type,
        "stream_url": stream_url,
        "youtube_url": channel.youtube_url,
        "youtube_embed_url": youtube_embed_url,
        "poster_image": absolute_media_url(request, channel.poster_image),
        "channel_logo": absolute_media_url(request, setting.channel_logo),
        "is_live": channel.is_live,
        "autoplay": setting.autoplay,
        "live_label": setting.live_label,
        "show_live_badge": setting.show_live_badge,
        "show_channel_logo": setting.show_channel_logo,
        "show_lower_third": setting.show_lower_third,
        "show_ticker": setting.show_ticker,
        "ticker_speed_seconds": setting.ticker_speed_seconds,
        "mobile_ticker_speed_seconds": setting.mobile_ticker_speed_seconds,
        "settings": serialize_live_tv_setting(request, setting),
        "web_url": request.build_absolute_uri(channel.get_absolute_url()),
        "ads": mobile_live_tv_ads(),
    }


def mobile_live_tv_ads():
    return [
        {
            "label": "The Up Media Services",
            "title": "Apna news portal banvaye",
            "text": "News website, admin panel, SEO, ads section aur deployment support.",
            "contact": "8279408396 | WhatsApp: 6397712918",
            "cta": "Call Now",
            "style": "services",
        },
        {
            "label": "The Up Media Academy",
            "title": "Learn Python and Web Development with Gen AI",
            "text": "Practical web development course for students and creators.",
            "contact": "8279408396 | WhatsApp: 6397712918",
            "cta": "Join Now",
            "style": "learning",
        },
        {
            "label": "Property Promotion",
            "title": "Plot, property aur local business promotion",
            "text": "The Up Media par local advertisement aur promotion.",
            "contact": "8279408396 | WhatsApp: 6397712918",
            "cta": "Advertise",
            "style": "property",
        },
    ]


def mobile_api_authorized(request):
    expected_key = getattr(settings, "MOBILE_UPLOAD_API_KEY", "")
    if not expected_key:
        return False

    auth_header = request.headers.get("Authorization", "")
    token = auth_header.removeprefix("Token ").removeprefix("Bearer ").strip()
    return token == expected_key or request.POST.get("api_key") == expected_key


def mobile_admin_user(request):
    auth_header = request.headers.get("Authorization", "")
    key = auth_header.removeprefix("Token ").removeprefix("Bearer ").strip()
    if not key:
        key = request.headers.get("X-Mobile-Admin-Token", "").strip()
    if not key:
        return None
    token = MobileAdminToken.objects.select_related("user").filter(key=key).first()
    if not token or not token.user.is_active or not token.user.is_superuser:
        return None
    token.last_used_at = timezone.now()
    token.save(update_fields=["last_used_at"])
    return token.user


def mobile_admin_required(request):
    user = mobile_admin_user(request)
    if not user:
        return None, JsonResponse({"detail": "Admin login required."}, status=401)
    return user, None


def channel_file_url(request, channel, field_name):
    return absolute_media_url(request, getattr(channel, field_name))


def serialize_channel_for_admin(request, channel):
    data = serialize_channel_for_mobile(request, channel)
    data.update(
        {
            "slug": channel.slug,
            "source_type": channel.source_type,
            "youtube_url": channel.youtube_url,
            "display_order": channel.display_order,
            "meta_title": channel.meta_title,
            "meta_description": channel.meta_description,
            "video_file_url": channel_file_url(request, channel, "video_file"),
            "poster_image_url": channel_file_url(request, channel, "poster_image"),
            "global_channel_logo_url": absolute_media_url(request, live_tv_setting().channel_logo),
            "updated_at": channel.updated_at.isoformat(),
        }
    )
    return data


def ffmpeg_binary():
    return getattr(settings, "FFMPEG_BINARY", "ffmpeg")


def ffmpeg_escape(text):
    safe_text = " ".join((text or "").split())
    replacements = {
        "\\": "\\\\",
        "'": "\\'",
        ":": "\\:",
        ",": "\\,",
        ";": "\\;",
        "[": "\\[",
        "]": "\\]",
        "%": "\\%",
    }
    for raw, escaped in replacements.items():
        safe_text = safe_text.replace(raw, escaped)
    return safe_text


def ffmpeg_text_file(text, prefix):
    safe_text = " ".join((text or "").split())
    text_dir = Path(tempfile.gettempdir()) / "theupmedia-render-text"
    text_dir.mkdir(parents=True, exist_ok=True)
    text_path = text_dir / f"{prefix}-{uuid4().hex}.txt"
    text_path.write_text(safe_text, encoding="utf-8")
    return text_path


def ffmpeg_path(path):
    return str(path).replace("\\", "/").replace(":", "\\:")


def ffmpeg_font_file():
    candidates = [
        getattr(settings, "FFMPEG_FONT_FILE", ""),
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansDevanagari-Bold.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansDevanagari-Regular.ttf",
        "/usr/share/fonts/truetype/lohit-devanagari/Lohit-Devanagari.ttf",
        "/usr/share/fonts/truetype/deva/lohit_hi.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate).replace("\\", "/").replace(":", "\\:")
    return ""


def ffmpeg_latin_font_file():
    candidates = [
        getattr(settings, "FFMPEG_LATIN_FONT_FILE", ""),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate).replace("\\", "/").replace(":", "\\:")
    return ffmpeg_font_file()


def has_devanagari(text):
    return any("\u0900" <= char <= "\u097f" for char in text or "")


def has_latin(text):
    return any(("A" <= char <= "Z") or ("a" <= char <= "z") for char in text or "")


def ffmpeg_font_arg_for_text(text, devanagari_font, latin_font):
    font = devanagari_font if has_devanagari(text) and not has_latin(text) else latin_font
    return f":fontfile='{font}'" if font else ""



def is_restricted_download_url(url):
    try:
        parsed = urlparse(url)
    except ValueError:
        return True
    host = (parsed.hostname or "").lower().removeprefix("www.")
    if parsed.scheme not in {"http", "https"} or not host:
        return True
    return any(host == domain or host.endswith(f".{domain}") for domain in RESTRICTED_DOWNLOAD_HOSTS)


def is_private_download_host(url):
    parsed = urlparse(url)
    host = parsed.hostname or ""
    try:
        addresses = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return True
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return True
    return False


def infer_download_media_type(content_type, filename):
    content_type = (content_type or "").split(";", 1)[0].strip().lower()
    suffix = Path(filename or "").suffix.lower()
    if content_type.startswith("video/") or suffix in {".mp4", ".mov", ".m4v", ".webm", ".mkv"}:
        return MediaDownload.MediaType.VIDEO
    if content_type.startswith("audio/") or suffix in {".mp3", ".m4a", ".aac", ".wav", ".ogg"}:
        return MediaDownload.MediaType.AUDIO
    return MediaDownload.MediaType.UNKNOWN


def filename_from_download_url(url, content_type=""):
    parsed = urlparse(url)
    raw_name = Path(parsed.path).name[:120]
    if raw_name and Path(raw_name).suffix.lower() in ALLOWED_DOWNLOAD_EXTENSIONS:
        return re.sub(r"[^A-Za-z0-9._() -]", "_", raw_name)
    extension = ".mp4"
    if (content_type or "").startswith("audio/"):
        extension = ".mp3"
    return f"theupmedia-download-{uuid4().hex[:12]}{extension}"


def validate_download_response(response, filename):
    content_type = response.headers.get("Content-Type", "")
    content_length = int(response.headers.get("Content-Length") or 0)
    media_type = infer_download_media_type(content_type, filename)
    if media_type == MediaDownload.MediaType.UNKNOWN:
        raise RuntimeError("Direct video/audio file URL required. Social page links or HTML pages are not supported.")
    max_mb = int(getattr(settings, "LIVE_TV_MEDIA_DOWNLOAD_MAX_MB", 700))
    if content_length and content_length > max_mb * 1024 * 1024:
        raise RuntimeError(f"File too large. Max allowed size is {max_mb} MB.")
    return media_type, content_length


def run_media_download_job(job_id):
    close_old_connections()
    job = MediaDownload.objects.get(pk=job_id)
    try:
        url = job.source_url.strip()
        if is_restricted_download_url(url):
            raise RuntimeError("YouTube, Instagram, Facebook, X page extraction supported nahi hai. Direct authorized media URL use kare.")
        if is_private_download_host(url):
            raise RuntimeError("Private/local server URL download allowed nahi hai.")

        request = Request(url, headers={"User-Agent": "TheUPMediaMobile/1.0"})
        with urlopen(request, timeout=30) as response:
            filename = filename_from_download_url(response.geturl(), response.headers.get("Content-Type", ""))
            media_type, total_size = validate_download_response(response, filename)
            temp_dir = Path(tempfile.gettempdir()) / "theupmedia-media-downloads"
            temp_dir.mkdir(parents=True, exist_ok=True)
            temp_path = temp_dir / f"{uuid4().hex}-{filename}"
            downloaded = 0
            with temp_path.open("wb") as output:
                while True:
                    chunk = response.read(1024 * 512)
                    if not chunk:
                        break
                    output.write(chunk)
                    downloaded += len(chunk)
                    if total_size:
                        MediaDownload.objects.filter(pk=job.pk).update(progress_percent=max(1, min(99, int(downloaded * 100 / total_size))))

            if not total_size:
                MediaDownload.objects.filter(pk=job.pk).update(progress_percent=90)
            with temp_path.open("rb") as downloaded_file:
                job.downloaded_file.save(filename, File(downloaded_file), save=False)
            job.media_type = media_type
            job.status = MediaDownload.Status.DONE
            job.progress_percent = 100
            job.error_message = ""
            job.save(update_fields=["downloaded_file", "media_type", "status", "progress_percent", "error_message", "updated_at"])
            temp_path.unlink(missing_ok=True)
    except Exception as exc:
        MediaDownload.objects.filter(pk=job_id).update(
            status=MediaDownload.Status.FAILED,
            error_message=str(exc),
            progress_percent=0,
        )
    finally:
        close_old_connections()

def video_duration_seconds(video_path):
    command = [
        ffmpeg_binary().replace("ffmpeg", "ffprobe"),
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        video_path,
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    try:
        return max(float(result.stdout.strip()), 1.0)
    except (TypeError, ValueError):
        return 1.0


def parse_ffmpeg_time(line):
    match = re.search(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)", line)
    if not match:
        return None
    hours, minutes, seconds = match.groups()
    return (int(hours) * 3600) + (int(minutes) * 60) + float(seconds)


def update_render_progress(job_id, percent):
    percent = max(0, min(99, int(percent)))
    SocialRenderedVideo.objects.filter(pk=job_id).update(progress_percent=percent)


def render_social_video_file(job):
    if not shutil.which(ffmpeg_binary()):
        raise RuntimeError("FFmpeg is not installed on server.")

    output_dir = Path(settings.MEDIA_ROOT) / "social-render" / "rendered"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"live-tv-render-{job.pk}-{uuid4().hex[:8]}.mp4"
    devanagari_font = ffmpeg_font_file()
    latin_font = ffmpeg_latin_font_file()

    text_files = []
    label_text = job.lower_third_label or "BREAKING NEWS"
    headline_text = job.headline or job.title
    ticker_text = job.ticker_text or "The Up Media"
    title_text = job.title
    label_file = ffmpeg_text_file(label_text, "label")
    headline_file = ffmpeg_text_file(headline_text, "headline")
    ticker_file = ffmpeg_text_file("    |    ".join([ticker_text] * 3), "ticker")
    title_file = ffmpeg_text_file(title_text, "title")
    text_files.extend([label_file, headline_file, ticker_file, title_file])
    label_font_arg = ffmpeg_font_arg_for_text(label_text, devanagari_font, latin_font)
    headline_font_arg = ffmpeg_font_arg_for_text(headline_text, devanagari_font, latin_font)
    ticker_font_arg = f":fontfile='{devanagari_font}'" if devanagari_font else ""
    title_font_arg = ffmpeg_font_arg_for_text(title_text, devanagari_font, latin_font)

    try:
        if job.render_format == "9:16":
            filter_complex = (
                "[0:v]scale=1080:607:force_original_aspect_ratio=increase,crop=1080:607,setsar=1[main];"
                "color=c=#08111f:s=1080x1920:d=999[bg];"
                "[bg][main]overlay=0:0[v0];"
                "[v0]drawbox=x=0:y=607:w=1080:h=72:color=white@0.94:t=fill,"
                "drawbox=x=0:y=607:w=220:h=72:color=#d71920@1:t=fill,"
                f"drawtext=textfile='{ffmpeg_path(label_file)}'{label_font_arg}:x=28:y=632:fontsize=32:fontcolor=white,"
                f"drawtext=textfile='{ffmpeg_path(headline_file)}'{headline_font_arg}:x=248:y=628:fontsize=34:fontcolor=#111827,"
                "drawbox=x=0:y=679:w=1080:h=54:color=#f8d24c@1:t=fill,"
                f"drawtext=textfile='{ffmpeg_path(ticker_file)}'{ticker_font_arg}:x=w-mod(t*135\\,w+tw):y=694:fontsize=26:fontcolor=#111827,"
                "drawbox=x=0:y=733:w=1080:h=360:color=#08111f@1:t=fill,"
                f"drawtext=textfile='{ffmpeg_path(title_file)}'{title_font_arg}:x=38:y=780:fontsize=46:fontcolor=white:box=1:boxcolor=#08111f@0.4,"
                "drawbox=x=38:y=930:w=1004:h=128:color=#13223a@1:t=fill,"
                "drawbox=x=38:y=930:w=1004:h=128:color=#28415f@1:t=2,"
                "drawtext=text='THE UP MEDIA LIVE TV FRAME':x=64:y=968:fontsize=34:fontcolor=#f8d24c,"
                "drawtext=text='Ready for social media sharing':x=64:y=1010:fontsize=26:fontcolor=white,"
                "format=yuv420p[vout]"
            )
        elif job.render_format == "fast_720p":
            filter_complex = (
                "[0:v]scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,setsar=1[main];"
                "[main]drawbox=x=0:y=561:w=1280:h=57:color=white@0.94:t=fill,"
                "drawbox=x=0:y=561:w=240:h=57:color=#d71920@1:t=fill,"
                f"drawtext=textfile='{ffmpeg_path(label_file)}'{label_font_arg}:x=23:y=581:fontsize=28:fontcolor=white,"
                f"drawtext=textfile='{ffmpeg_path(headline_file)}'{headline_font_arg}:x=260:y=577:fontsize=31:fontcolor=#111827,"
                "drawbox=x=0:y=619:w=1280:h=39:color=#f8d24c@1:t=fill,"
                f"drawtext=textfile='{ffmpeg_path(ticker_file)}'{ticker_font_arg}:x=w-mod(t*170\\,w+tw):y=630:fontsize=20:fontcolor=#111827,"
                "drawbox=x=0:y=657:w=1280:h=63:color=#08111f@0.96:t=fill,"
                f"drawtext=textfile='{ffmpeg_path(title_file)}'{title_font_arg}:x=28:y=676:fontsize=29:fontcolor=white,"
                "drawbox=x=1007:y=25:w=153:h=77:color=white@0.96:t=fill,"
                "drawtext=text='THE UP':x=1027:y=40:fontsize=24:fontcolor=#d71920,"
                "drawbox=x=1007:y=64:w=153:h=38:color=#08111f@1:t=fill,"
                "drawtext=text='MEDIA':x=1039:y=72:fontsize=23:fontcolor=white,"
                "drawbox=x=25:y=25:w=100:h=40:color=#d71920@1:t=fill,"
                "drawtext=text='LIVE':x=50:y=34:fontsize=23:fontcolor=white,"
                "format=yuv420p[vout]"
            )
        else:
            filter_complex = (
                "[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,setsar=1[main];"
                "[main]drawbox=x=0:y=842:w=1920:h=86:color=white@0.94:t=fill,"
                "drawbox=x=0:y=842:w=360:h=86:color=#d71920@1:t=fill,"
                f"drawtext=textfile='{ffmpeg_path(label_file)}'{label_font_arg}:x=34:y=872:fontsize=42:fontcolor=white,"
                f"drawtext=textfile='{ffmpeg_path(headline_file)}'{headline_font_arg}:x=390:y=866:fontsize=46:fontcolor=#111827,"
                "drawbox=x=0:y=928:w=1920:h=58:color=#f8d24c@1:t=fill,"
                f"drawtext=textfile='{ffmpeg_path(ticker_file)}'{ticker_font_arg}:x=w-mod(t*220\\,w+tw):y=944:fontsize=30:fontcolor=#111827,"
                "drawbox=x=0:y=986:w=1920:h=94:color=#08111f@0.96:t=fill,"
                f"drawtext=textfile='{ffmpeg_path(title_file)}'{title_font_arg}:x=42:y=1014:fontsize=44:fontcolor=white,"
                "drawbox=x=1510:y=38:w=230:h=116:color=white@0.96:t=fill,"
                "drawtext=text='THE UP':x=1540:y=60:fontsize=36:fontcolor=#d71920,"
                "drawbox=x=1510:y=96:w=230:h=58:color=#08111f@1:t=fill,"
                "drawtext=text='MEDIA':x=1558:y=108:fontsize=34:fontcolor=white,"
                "drawbox=x=38:y=38:w=150:h=60:color=#d71920@1:t=fill,"
                "drawtext=text='LIVE':x=76:y=52:fontsize=34:fontcolor=white,"
                "format=yuv420p[vout]"
            )

        use_nvenc = getattr(settings, "LIVE_TV_RENDER_ENCODER", "cpu").lower() == "nvenc"
        if use_nvenc:
            encoder_args = [
                "-c:v",
                "h264_nvenc",
                "-preset",
                getattr(settings, "LIVE_TV_RENDER_NVENC_PRESET", "p1"),
                "-cq",
                str(getattr(settings, "LIVE_TV_RENDER_NVENC_CQ", "28")),
            ]
        else:
            video_preset = "ultrafast" if job.render_format == "fast_720p" else "veryfast"
            video_crf = "28" if job.render_format == "fast_720p" else "23"
            encoder_args = [
                "-c:v",
                "libx264",
                "-preset",
                video_preset,
                "-crf",
                video_crf,
            ]

        command = [
            ffmpeg_binary(),
            "-y",
            "-i",
            job.original_video.path,
            "-filter_complex",
            filter_complex,
            "-map",
            "[vout]",
            "-map",
            "0:a?",
            *encoder_args,
            "-c:a",
            "aac",
            "-shortest",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
        duration = video_duration_seconds(job.original_video.path)
        process = subprocess.Popen(command, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        stderr_tail = []
        for line in process.stderr:
            stderr_tail.append(line)
            stderr_tail = stderr_tail[-30:]
            current_time = parse_ffmpeg_time(line)
            if current_time is not None:
                update_render_progress(job.pk, min(99, (current_time / duration) * 100))

        process.wait(timeout=900)
        if process.returncode != 0:
            raise RuntimeError(("".join(stderr_tail) or "FFmpeg render failed.")[-1200:])

        with output_path.open("rb") as rendered_file:
            job.rendered_video.save(output_path.name, File(rendered_file), save=False)
        job.status = SocialRenderedVideo.Status.DONE
        job.progress_percent = 100
        job.error_message = ""
        job.save(update_fields=["rendered_video", "status", "progress_percent", "error_message", "updated_at"])
        return job
    finally:
        for text_file in text_files:
            text_file.unlink(missing_ok=True)


def run_social_render_job(job_id):
    close_old_connections()
    job = SocialRenderedVideo.objects.get(pk=job_id)
    try:
        update_render_progress(job.pk, 1)
        render_social_video_file(job)
    except Exception as exc:
        SocialRenderedVideo.objects.filter(pk=job_id).update(
            status=SocialRenderedVideo.Status.FAILED,
            error_message=str(exc),
            progress_percent=0,
        )
    finally:
        close_old_connections()



def serialize_media_download(request, job):
    file_url = request.build_absolute_uri(job.downloaded_file.url) if job.downloaded_file else ""
    return {
        "id": job.pk,
        "title": job.title,
        "source_url": job.source_url,
        "media_type": job.media_type,
        "status": job.status,
        "progress_percent": job.progress_percent,
        "file_url": file_url,
        "error": job.error_message,
        "created_at": job.created_at.isoformat(),
    }

def serialize_render_job(request, job):
    rendered_url = request.build_absolute_uri(job.rendered_video.url) if job.rendered_video else ""
    original_url = request.build_absolute_uri(job.original_video.url) if job.original_video else ""
    return {
        "id": job.pk,
        "status": job.status,
        "progress_percent": job.progress_percent,
        "title": job.title,
        "headline": job.headline,
        "ticker_text": job.ticker_text,
        "lower_third_label": job.lower_third_label,
        "render_format": job.render_format,
        "original_video_url": original_url,
        "rendered_video_url": rendered_url,
        "error": job.error_message,
        "created_at": job.created_at.isoformat(),
    }


def serialize_mobile_upload(request, upload):
    return {
        "id": upload.pk,
        "title": upload.title,
        "description": upload.description,
        "status": upload.status,
        "status_label": upload.get_status_display(),
        "uploaded_by_name": upload.uploaded_by_name,
        "uploaded_by_phone": upload.uploaded_by_phone,
        "video_url": request.build_absolute_uri(upload.video.url),
        "created_at": upload.created_at.isoformat(),
    }


def delete_file_field(file_field):
    if file_field:
        file_field.delete(save=False)


def manageable_uploads_for(user):
    return MobileVideoUpload.objects.filter(Q(uploaded_by=user) | Q(uploaded_by__isnull=True))


def manageable_render_jobs_for(user):
    return SocialRenderedVideo.objects.filter(Q(created_by=user) | Q(created_by__isnull=True))


def manageable_media_downloads_for(user):
    return MediaDownload.objects.filter(Q(created_by=user) | Q(created_by__isnull=True))


def superuser_required(view_func):
    return login_required(user_passes_test(lambda user: user.is_superuser)(view_func))


def live_tv_home(request):
    channels = LiveTVChannel.objects.filter(is_active=True)
    active_channel = channels.first()
    force_autoplay = request.GET.get("autoplay") == "1"
    return render(request, "live_tv/live_tv_home.html", live_tv_context(active_channel, channels, force_autoplay))


def live_tv_detail(request, slug):
    channels = LiveTVChannel.objects.filter(is_active=True)
    active_channel = get_object_or_404(channels, slug=slug)
    force_autoplay = request.GET.get("autoplay") == "1"
    return render(request, "live_tv/live_tv_home.html", live_tv_context(active_channel, channels, force_autoplay))


@require_GET
def current_live_tv_api(request):
    channels = LiveTVChannel.objects.filter(is_active=True)
    active_channel = channels.filter(is_live=True).first() or channels.first()
    if not active_channel:
        return JsonResponse({"detail": "No active live TV channel found."}, status=404)
    return JsonResponse(serialize_channel_for_mobile(request, active_channel))


@csrf_exempt
@require_POST
def mobile_video_upload_api(request):
    admin_user = mobile_admin_user(request)
    is_admin = bool(admin_user)
    if not is_admin and not getattr(settings, "MOBILE_UPLOAD_API_KEY", ""):
        return JsonResponse({"detail": "Mobile upload API token is not configured."}, status=503)
    if not is_admin and not mobile_api_authorized(request):
        return JsonResponse({"detail": "Invalid mobile upload API token."}, status=403)

    video = request.FILES.get("video")
    title = request.POST.get("title", "").strip()

    if not video:
        return JsonResponse({"detail": "Video file is required."}, status=400)
    if not title:
        title = Path(video.name).stem[:180] or "Mobile video upload"

    upload = MobileVideoUpload.objects.create(
        title=title,
        description=request.POST.get("description", "").strip(),
        video=video,
        uploaded_by=admin_user if is_admin else None,
        uploaded_by_name=request.POST.get("uploaded_by_name", "").strip(),
        uploaded_by_phone=request.POST.get("uploaded_by_phone", "").strip(),
        device_info=request.POST.get("device_info", "").strip()[:220],
    )

    return JsonResponse(
        {
            "id": upload.pk,
            "title": upload.title,
            "status": upload.status,
            "video_url": request.build_absolute_uri(upload.video.url),
        },
        status=201,
    )


@csrf_exempt
@require_POST
def mobile_admin_login_api(request):
    username = request.POST.get("username", "").strip()
    password = request.POST.get("password", "")
    device_name = request.POST.get("device_name", "Mobile App").strip()

    user = authenticate(request, username=username, password=password)
    if not user:
        return JsonResponse({"detail": "Invalid username or password."}, status=400)
    if not user.is_active or not user.is_superuser:
        return JsonResponse({"detail": "Only superuser admins can operate Live TV from mobile."}, status=403)

    token = MobileAdminToken.create_for_user(user, device_name=device_name)
    return JsonResponse(
        {
            "token": token.key,
            "user": {
                "id": user.pk,
                "username": user.get_username(),
                "name": user.get_full_name() or user.get_username(),
                "is_superuser": user.is_superuser,
            },
        }
    )


@csrf_exempt
@require_POST
def mobile_admin_logout_api(request):
    auth_header = request.headers.get("Authorization", "")
    key = auth_header.removeprefix("Token ").removeprefix("Bearer ").strip()
    if key:
        MobileAdminToken.objects.filter(key=key).delete()
    return JsonResponse({"ok": True})


@require_GET
def mobile_admin_dashboard_api(request):
    user, error = mobile_admin_required(request)
    if error:
        return error

    channels = LiveTVChannel.objects.all()
    uploads = manageable_uploads_for(user)[:50]
    rendered_videos = manageable_render_jobs_for(user)[:50]
    media_downloads = manageable_media_downloads_for(user)[:50]
    settings_obj = live_tv_setting()
    return JsonResponse(
        {
            "user": {"id": user.pk, "username": user.get_username(), "name": user.get_full_name() or user.get_username()},
            "settings": serialize_live_tv_setting(request, settings_obj),
            "facebook_live": serialize_facebook_live_setting(facebook_live_setting()),
            "channels": [serialize_channel_for_admin(request, channel) for channel in channels],
            "mobile_uploads": [serialize_mobile_upload(request, upload) for upload in uploads],
            "rendered_videos": [serialize_render_job(request, job) for job in rendered_videos],
            "media_downloads": [serialize_media_download(request, job) for job in media_downloads],
            "source_types": list(LiveTVChannel.SourceType.values),
        }
    )



@csrf_exempt
@require_POST
def mobile_admin_settings_save_api(request):
    _user, error = mobile_admin_required(request)
    if error:
        return error

    setting = live_tv_setting()
    setting.name = request.POST.get("name", setting.name).strip()[:120] or setting.name
    setting.live_label = request.POST.get("live_label", setting.live_label).strip()[:40] or setting.live_label
    setting.default_lower_third_label = request.POST.get("default_lower_third_label", setting.default_lower_third_label).strip()[:60] or setting.default_lower_third_label
    setting.default_headline = request.POST.get("default_headline", setting.default_headline).strip()[:180] or setting.default_headline
    setting.default_ticker_label = request.POST.get("default_ticker_label", setting.default_ticker_label).strip()[:60] or setting.default_ticker_label
    setting.default_ticker_text = request.POST.get("default_ticker_text", setting.default_ticker_text).strip()[:260] or setting.default_ticker_text
    if "ticker_speed_seconds" in request.POST:
        try:
            setting.ticker_speed_seconds = max(6, min(120, int(request.POST.get("ticker_speed_seconds") or setting.ticker_speed_seconds)))
        except (TypeError, ValueError):
            pass
    if "mobile_ticker_speed_seconds" in request.POST:
        try:
            setting.mobile_ticker_speed_seconds = max(6, min(120, int(request.POST.get("mobile_ticker_speed_seconds") or setting.mobile_ticker_speed_seconds)))
        except (TypeError, ValueError):
            pass
    for field in ["show_live_badge", "show_channel_logo", "show_lower_third", "show_ticker", "autoplay"]:
        if field in request.POST:
            setattr(setting, field, request.POST.get(field) in {"1", "true", "on", "yes"})
    if request.FILES.get("channel_logo"):
        delete_file_field(setting.channel_logo)
        setting.channel_logo = request.FILES["channel_logo"]
    setting.save()
    return JsonResponse({"settings": serialize_live_tv_setting(request, setting)})

@csrf_exempt
@require_POST
def mobile_admin_channel_save_api(request):
    _user, error = mobile_admin_required(request)
    if error:
        return error

    channel_id = request.POST.get("id") or request.POST.get("channel_id")
    instance = LiveTVChannel.objects.filter(pk=channel_id).first() if channel_id else None

    data = request.POST.copy()
    data.setdefault("title", "The Up Media Live TV")
    data.setdefault("source_type", LiveTVChannel.SourceType.YOUTUBE)
    settings_obj = live_tv_setting()
    data.setdefault("lower_third_label", settings_obj.default_lower_third_label)
    data.setdefault("headline", data.get("title", settings_obj.default_headline))
    data.setdefault("ticker_label", settings_obj.default_ticker_label)
    data.setdefault("ticker_text", "")
    data.setdefault("display_order", "0")
    data["is_active"] = "on"
    data["is_live"] = "on"

    form = LiveTVChannelForm(data, request.FILES, instance=instance)
    if not form.is_valid():
        return JsonResponse({"detail": "Please correct the channel fields.", "errors": form.errors}, status=400)

    channel = form.save()
    return JsonResponse({"channel": serialize_channel_for_admin(request, channel)})


@csrf_exempt
@require_POST
def mobile_admin_channel_delete_api(request, pk):
    _user, error = mobile_admin_required(request)
    if error:
        return error

    channel = get_object_or_404(LiveTVChannel, pk=pk)
    channel.delete()
    return JsonResponse({"ok": True})


@csrf_exempt
@require_POST
def mobile_admin_upload_update_api(request, pk):
    user, error = mobile_admin_required(request)
    if error:
        return error

    upload = get_object_or_404(manageable_uploads_for(user), pk=pk)
    title = request.POST.get("title", "").strip()
    description = request.POST.get("description", "").strip()
    if title:
        upload.title = title[:180]
    upload.description = description
    upload.save(update_fields=["title", "description", "updated_at"])
    return JsonResponse({"upload": serialize_mobile_upload(request, upload)})


@csrf_exempt
@require_POST
def mobile_admin_upload_delete_api(request, pk):
    user, error = mobile_admin_required(request)
    if error:
        return error

    upload = get_object_or_404(manageable_uploads_for(user), pk=pk)
    delete_file_field(upload.video)
    upload.delete()
    return JsonResponse({"ok": True})


@csrf_exempt
@require_POST
def mobile_admin_rendered_video_update_api(request, pk):
    user, error = mobile_admin_required(request)
    if error:
        return error

    job = get_object_or_404(manageable_render_jobs_for(user), pk=pk)
    title = request.POST.get("title", "").strip()
    headline = request.POST.get("headline", "").strip()
    ticker_text = request.POST.get("ticker_text", "").strip()
    lower_third_label = request.POST.get("lower_third_label", "").strip()
    if title:
        job.title = title[:180]
    job.headline = headline[:180]
    job.ticker_text = ticker_text[:260]
    if lower_third_label:
        job.lower_third_label = lower_third_label[:60]
    job.save(update_fields=["title", "headline", "ticker_text", "lower_third_label", "updated_at"])
    return JsonResponse({"rendered_video": serialize_render_job(request, job)})


@csrf_exempt
@require_POST
def mobile_admin_rendered_video_delete_api(request, pk):
    user, error = mobile_admin_required(request)
    if error:
        return error

    job = get_object_or_404(manageable_render_jobs_for(user), pk=pk)
    delete_file_field(job.original_video)
    delete_file_field(job.rendered_video)
    job.delete()
    return JsonResponse({"ok": True})



@csrf_exempt
@require_POST
def mobile_admin_media_download_start_api(request):
    user, error = mobile_admin_required(request)
    if error:
        return error

    source_url = request.POST.get("url", "").strip()
    title = request.POST.get("title", "").strip()
    if not source_url:
        return JsonResponse({"detail": "URL is required."}, status=400)
    if is_restricted_download_url(source_url):
        return JsonResponse({"detail": "Direct video/audio file URL required. YouTube, Instagram, Facebook, X page extraction supported nahi hai."}, status=400)
    if not title:
        title = Path(urlparse(source_url).path).stem[:180] or "Media download"

    job = MediaDownload.objects.create(
        title=title[:180],
        source_url=source_url,
        created_by=user,
    )
    queue_backend = enqueue_media_download_job(job.pk)
    data = serialize_media_download(request, job)
    data["queue_backend"] = queue_backend
    return JsonResponse(data, status=202)


@require_GET
def mobile_admin_media_download_status_api(request, pk):
    user, error = mobile_admin_required(request)
    if error:
        return error

    job = get_object_or_404(manageable_media_downloads_for(user), pk=pk)
    return JsonResponse(serialize_media_download(request, job))


@csrf_exempt
@require_POST
def mobile_admin_media_download_update_api(request, pk):
    user, error = mobile_admin_required(request)
    if error:
        return error

    job = get_object_or_404(manageable_media_downloads_for(user), pk=pk)
    title = request.POST.get("title", "").strip()
    if title:
        job.title = title[:180]
        job.save(update_fields=["title", "updated_at"])
    return JsonResponse({"media_download": serialize_media_download(request, job)})


@csrf_exempt
@require_POST
def mobile_admin_media_download_delete_api(request, pk):
    user, error = mobile_admin_required(request)
    if error:
        return error

    job = get_object_or_404(manageable_media_downloads_for(user), pk=pk)
    delete_file_field(job.downloaded_file)
    job.delete()
    return JsonResponse({"ok": True})

@csrf_exempt
@require_POST
def mobile_admin_render_social_video_api(request):
    user, error = mobile_admin_required(request)
    if error:
        return error

    video = request.FILES.get("video")
    if not video:
        return JsonResponse({"detail": "Video file is required."}, status=400)

    active_channel = LiveTVChannel.objects.filter(is_active=True, is_live=True).first() or LiveTVChannel.objects.filter(is_active=True).first()
    title = request.POST.get("title", "").strip() or (active_channel.title if active_channel else Path(video.name).stem)
    headline = request.POST.get("headline", "").strip() or (active_channel.headline if active_channel else title)
    ticker_text = request.POST.get("ticker_text", "").strip() or (active_channel.ticker_text if active_channel else "The Up Media")
    lower_third_label = request.POST.get("lower_third_label", "").strip() or (active_channel.lower_third_label if active_channel else "BREAKING NEWS")
    render_format = request.POST.get("render_format", "16:9").strip()
    if render_format not in {"fast_720p", "16:9", "9:16"}:
        render_format = "16:9"

    job = SocialRenderedVideo.objects.create(
        title=title[:180],
        headline=headline[:180],
        ticker_text=ticker_text[:260],
        lower_third_label=lower_third_label[:60],
        render_format=render_format,
        original_video=video,
        created_by=user,
    )

    queue_backend = enqueue_social_render_job(job.pk)

    return JsonResponse(
        {
            "id": job.pk,
            "status": job.status,
            "progress_percent": job.progress_percent,
            "title": job.title,
            "original_video_url": request.build_absolute_uri(job.original_video.url),
            "queue_backend": queue_backend,
        },
        status=202,
    )


@require_GET
def mobile_admin_render_social_video_status_api(request, pk):
    _user, error = mobile_admin_required(request)
    if error:
        return error

    job = get_object_or_404(SocialRenderedVideo, pk=pk)
    return JsonResponse(serialize_render_job(request, job))



@superuser_required
def media_download_page(request):
    if request.method == "POST":
        source_url = request.POST.get("url", "").strip()
        title = request.POST.get("title", "").strip()
        if not source_url:
            messages.error(request, "Download URL required.")
            return redirect("live_tv:media_downloads")
        if is_restricted_download_url(source_url):
            messages.error(request, "Direct video/audio file URL required. YouTube, Instagram, Facebook, X page extraction supported nahi hai.")
            return redirect("live_tv:media_downloads")
        if not title:
            title = Path(urlparse(source_url).path).stem[:180] or "Media download"
        job = MediaDownload.objects.create(title=title[:180], source_url=source_url, created_by=request.user)
        queue_backend = enqueue_media_download_job(job.pk)
        messages.success(request, f"Download job start ho gaya ({queue_backend}). Status neeche dekhe.")
        return redirect("live_tv:media_downloads")

    jobs = manageable_media_downloads_for(request.user)[:50]
    return render(request, "live_tv/media_downloads.html", {"jobs": jobs})


@superuser_required
@require_POST
def delete_media_download(request, pk):
    job = get_object_or_404(manageable_media_downloads_for(request.user), pk=pk)
    delete_file_field(job.downloaded_file)
    job.delete()
    messages.success(request, "Download job delete ho gaya.")
    return redirect("live_tv:media_downloads")

@superuser_required
def dashboard(request):
    channels = LiveTVChannel.objects.all()
    selected_id = request.GET.get("edit")
    instance = channels.filter(pk=selected_id).first() if selected_id else None

    if request.method == "POST":
        instance = channels.filter(pk=request.POST.get("channel_id")).first() if request.POST.get("channel_id") else None
        form = LiveTVChannelForm(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            channel = form.save()
            messages.success(request, "Live TV channel saved.")
            return redirect(f"{request.path}?edit={channel.pk}")
    else:
        form = LiveTVChannelForm(instance=instance)

    preview_channel = instance or channels.first()
    return render(
        request,
        "live_tv/dashboard.html",
        {
            "channels": channels,
            "form": form,
            "selected_channel": instance,
            "preview_channel": preview_channel,
            "mobile_uploads": MobileVideoUpload.objects.all()[:10],
        },
    )


@superuser_required
@require_POST
def delete_channel(request, pk):
    channel = get_object_or_404(LiveTVChannel, pk=pk)
    channel.delete()
    messages.success(request, "Live TV channel deleted.")
    return redirect("live_tv:dashboard")
@csrf_exempt
@require_POST
def mobile_admin_facebook_live_save_api(request):
    _user, error = mobile_admin_required(request)
    if error:
        return error

    setting = facebook_live_setting()
    setting.name = request.POST.get("name", setting.name).strip()[:120] or setting.name
    setting.server_url = request.POST.get("server_url", setting.server_url).strip()[:500] or setting.server_url
    stream_key = request.POST.get("stream_key", "").strip()
    if stream_key:
        setting.stream_key = stream_key[:500]
    if "is_enabled" in request.POST:
        setting.is_enabled = request.POST.get("is_enabled") in {"1", "true", "on", "yes"}
    setting.save()
    return JsonResponse({"facebook_live": serialize_facebook_live_setting(setting)})


@csrf_exempt
@require_POST
def mobile_admin_facebook_live_start_api(request):
    _user, error = mobile_admin_required(request)
    if error:
        return error

    setting = facebook_live_setting()
    if not setting.is_enabled:
        return JsonResponse({"detail": "Facebook Live is disabled. Enable it first."}, status=400)
    try:
        setting = start_facebook_live_process(setting)
    except Exception as exc:
        setting.status = FacebookLiveSetting.Status.FAILED
        setting.last_error = str(exc)
        setting.process_id = None
        setting.stopped_at = timezone.now()
        setting.save(update_fields=["status", "last_error", "process_id", "stopped_at", "updated_at"])
        return JsonResponse({"detail": "Facebook Live start failed.", "error": str(exc), "facebook_live": serialize_facebook_live_setting(setting)}, status=400)
    return JsonResponse({"facebook_live": serialize_facebook_live_setting(setting)})


@csrf_exempt
@require_POST
def mobile_admin_facebook_live_stop_api(request):
    _user, error = mobile_admin_required(request)
    if error:
        return error

    setting = stop_facebook_live_process(facebook_live_setting())
    return JsonResponse({"facebook_live": serialize_facebook_live_setting(setting)})


@require_GET
def mobile_admin_facebook_live_status_api(request):
    _user, error = mobile_admin_required(request)
    if error:
        return error

    return JsonResponse({"facebook_live": serialize_facebook_live_setting(facebook_live_setting())})
