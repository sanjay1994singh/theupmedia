import ipaddress
import logging
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
from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.files.base import ContentFile
from django.db import close_old_connections, transaction
from django.db.models.deletion import ProtectedError
from django.db.models import F, Q
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_POST

from .forms import LiveTVChannelForm
from .hls import validate_uploaded_video
from .models import AppHomeSetting, AppMenu, ChannelFollow, FacebookLiveSetting, HomeContent, HomeUtility, LiveTVCategory, LiveTVCity, LiveTVChannel, LiveTVPlaylistItem, LiveTVSetting, LiveTVState, MediaDownload, MobileAdminToken, NewsTickerSetting, ShortsComment, ShortsLike, ShortsVideo, SocialRenderedVideo
from .services import calculate_current_playback, get_main_live_channel, update_playlist_item
from news.models import Article


logger = logging.getLogger(__name__)

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


def enqueue_short_hls_job(short_id):
    if getattr(settings, "LIVE_TV_RENDER_USE_CELERY", True):
        try:
            from .tasks import process_short_hls_task

            process_short_hls_task.delay(short_id)
            return "celery"
        except Exception as exc:
            ShortsVideo.objects.filter(pk=short_id).update(
                processing_error=f"Celery enqueue failed, fallback thread started: {exc}",
            )

    import threading

    from .hls import convert_short_to_hls

    threading.Thread(target=convert_short_to_hls, args=(short_id,), daemon=True).start()
    return "thread"


def enqueue_live_channel_hls_job(channel_id):
    if getattr(settings, "LIVE_TV_RENDER_USE_CELERY", True):
        try:
            from .tasks import process_live_channel_hls_task

            process_live_channel_hls_task.delay(channel_id)
            return "celery"
        except Exception as exc:
            LiveTVChannel.objects.filter(pk=channel_id).update(
                processing_error=f"Celery enqueue failed, fallback thread started: {exc}",
            )

    import threading

    from .hls import convert_live_channel_to_hls

    threading.Thread(target=convert_live_channel_to_hls, args=(channel_id,), daemon=True).start()
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
    if active_channel and active_channel.source_type == LiveTVChannel.SourceType.PLAYLIST:
        playlist_state = calculate_current_playback(active_channel)
        if playlist_state:
            active_channel = playlist_state["video"]
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
        "news_ticker": news_ticker_setting(),
    }


def absolute_media_url(request, file_obj):
    if not file_obj:
        return ""
    return request.build_absolute_uri(file_obj.url)


def absolute_media_path_url(request, media_path):
    if not media_path:
        return ""
    base_url = str(settings.MEDIA_URL or "/media/")
    if not base_url.endswith("/"):
        base_url += "/"
    if base_url.startswith("http://") or base_url.startswith("https://"):
        return f"{base_url}{str(media_path).lstrip('/')}"
    return request.build_absolute_uri(f"{base_url}{str(media_path).lstrip('/')}")




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
    ticker_setting = news_ticker_setting()
    label_text = channel.lower_third_label or setting.default_lower_third_label
    headline_text = channel.headline or setting.default_headline
    ticker_text = ticker_setting.text or setting.default_ticker_text
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


def news_ticker_setting():
    return NewsTickerSetting.get_solo()


def serialize_live_tv_setting(request, setting):
    ticker = news_ticker_setting()
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
        "default_ticker_label": ticker.label,
        "default_ticker_text": ticker.text,
        "ticker_speed_seconds": ticker.speed_seconds,
        "mobile_ticker_speed_seconds": ticker.mobile_speed_seconds,
        "ticker_style": ticker.style,
        "updated_at": setting.updated_at.isoformat(),
    }

def ticker_items_from_text(text):
    if not text:
        return []
    raw_items = text.replace("\r", "\n").replace("|", "\n").split("\n")
    return [item.strip() for item in raw_items if item.strip()]


def serialize_channel_for_mobile(request, channel):
    setting = live_tv_setting()
    ticker_setting = news_ticker_setting()
    player_type = channel.player_source_type
    stream_url = ""
    youtube_embed_url = ""

    hls_url = absolute_media_path_url(request, channel.hls_master_url)
    mp4_url = absolute_media_url(request, channel.video_file)

    if player_type == LiveTVChannel.SourceType.DIRECT:
        stream_url = hls_url or mp4_url
        if hls_url:
            player_type = LiveTVChannel.SourceType.HLS
    elif player_type == LiveTVChannel.SourceType.HLS:
        stream_url = channel.stream_url
    elif player_type == LiveTVChannel.SourceType.YOUTUBE:
        youtube_embed_url = channel.youtube_embed_url

    ticker = ticker_items_from_text(ticker_setting.text)

    return {
        "id": channel.pk,
        "title": channel.title,
        "description": channel.description,
        "category": {"id": channel.category_id, "name": channel.category.name} if channel.category_id else None,
        "category_id": channel.category_id,
        "category_name": channel.category.name if channel.category_id else "",
        "state": {"id": channel.state_id, "name": channel.state.name} if channel.state_id else None,
        "state_id": channel.state_id,
        "state_name": channel.state.name if channel.state_id else "",
        "city": {"id": channel.city_id, "name": channel.city.name} if channel.city_id else None,
        "city_id": channel.city_id,
        "city_name": channel.city.name if channel.city_id else "",
        "headline": channel.headline or "",
        "lower_third_label": channel.lower_third_label or "",
        "ticker_label": ticker_setting.label or setting.default_ticker_label,
        "ticker": ticker,
        "player_type": player_type,
        "stream_url": stream_url,
        "mp4_url": mp4_url,
        "hls_url": hls_url,
        "processing_status": channel.hls_status,
        "hls_status": channel.hls_status,
        "processing_error": channel.processing_error,
        "duration": channel.duration,
        "youtube_url": channel.youtube_url,
        "youtube_embed_url": youtube_embed_url,
        "poster_image": absolute_media_url(request, channel.poster_image),
        "channel_logo": absolute_media_url(request, setting.channel_logo),
        "is_live": channel.is_live,
        "autoplay": setting.autoplay,
        "live_label": setting.live_label,
        "show_live_badge": setting.show_live_badge,
        "show_channel_logo": setting.show_channel_logo,
        "show_lower_third": setting.show_lower_third and bool((channel.lower_third_label or "").strip() or (channel.headline or "").strip()),
        "show_ticker": setting.show_ticker,
        "ticker_speed_seconds": ticker_setting.speed_seconds,
        "mobile_ticker_speed_seconds": ticker_setting.mobile_speed_seconds,
        "ticker_style": ticker_setting.style,
        "settings": serialize_live_tv_setting(request, setting),
        "web_url": request.build_absolute_uri(channel.get_absolute_url()),
        "ads": mobile_live_tv_ads(),
    }


def serialize_synced_live_state(request, channel, server_time=None):
    server_time = server_time or timezone.now()
    state = calculate_current_playback(channel, at=server_time)
    if not state:
        return None
    video = state["video"]
    setting = live_tv_setting()
    ticker_setting = news_ticker_setting()
    hls_url = absolute_media_path_url(request, video.hls_master_url)
    video_url = absolute_media_url(request, video.video_file)
    stream_url = hls_url or video_url
    next_video = state["next_entry"].video if state.get("next_entry") else None
    ticker = ticker_items_from_text(ticker_setting.text)
    return {
        "is_live": True,
        "is_live_synced": True,
        "channel_id": channel.pk,
        "channel_slug": channel.slug,
        "channel_title": channel.title,
        "channel": {"id": channel.pk, "slug": channel.slug, "title": channel.title},
        "source_type": LiveTVChannel.SourceType.PLAYLIST,
        "player_type": LiveTVChannel.SourceType.HLS if hls_url else LiveTVChannel.SourceType.DIRECT,
        "video_id": video.pk,
        "title": video.title,
        "headline": video.headline or "",
        "description": video.description or "",
        "video_url": video_url,
        "mp4_url": video_url,
        "hls_url": hls_url,
        "stream_url": stream_url,
        "poster_url": absolute_media_url(request, video.poster_image),
        "poster_image": absolute_media_url(request, video.poster_image),
        "video_duration": state["entry"].duration_seconds,
        "duration": state["entry"].duration_seconds,
        "seek_position": round(state["seek_position"], 3),
        "video_started_at": state["video_started_at"].isoformat(),
        "server_time": server_time.isoformat(),
        "playlist_total_duration": state["playlist_total_duration"],
        "playlist_version": state["playlist_version"],
        "loop_enabled": channel.loop_enabled,
        "next_video_id": next_video.pk if next_video else None,
        "next_video": {"id": next_video.pk, "title": next_video.title} if next_video else None,
        "ticker_label": ticker_setting.label or setting.default_ticker_label,
        "default_ticker_label": ticker_setting.label or setting.default_ticker_label,
        "ticker_text": ticker_setting.text or setting.default_ticker_text,
        "default_ticker_text": ticker_setting.text or setting.default_ticker_text,
        "ticker": ticker,
        "lower_third_label": video.lower_third_label or "",
        "show_lower_third": setting.show_lower_third and bool((video.lower_third_label or "").strip() or (video.headline or "").strip()),
        "show_live_badge": setting.show_live_badge,
        "show_channel_logo": setting.show_channel_logo,
        "show_ticker": setting.show_ticker,
        "channel_logo": absolute_media_url(request, setting.channel_logo),
        "live_label": setting.live_label,
        "autoplay": setting.autoplay,
        "ticker_speed_seconds": ticker_setting.speed_seconds,
        "mobile_ticker_speed_seconds": ticker_setting.mobile_speed_seconds,
        "ticker_style": ticker_setting.style,
        "settings": serialize_live_tv_setting(request, setting),
        "ads": mobile_live_tv_ads(),
    }


def serialize_live_fallback(request, channel, server_time=None):
    server_time = server_time or timezone.now()
    data = serialize_channel_for_mobile(request, channel)
    data.update(
        {
            "is_live": bool(data.get("stream_url") or data.get("youtube_embed_url")),
            "is_live_synced": False,
            "channel_id": channel.pk,
            "channel_slug": channel.slug,
            "channel_title": channel.title,
            "video_id": channel.pk if data.get("stream_url") else None,
            "video_url": data.get("mp4_url") or data.get("stream_url") or "",
            "poster_url": data.get("poster_image") or "",
            "video_duration": channel.effective_duration_seconds,
            "seek_position": 0,
            "video_started_at": server_time.isoformat(),
            "server_time": server_time.isoformat(),
            "playlist_total_duration": 0,
            "playlist_version": channel.playlist_version,
            "loop_enabled": channel.loop_enabled,
            "next_video_id": None,
            "ticker_text": news_ticker_setting().text,
        }
    )
    return data


def serialize_home_content(request, content):
    thumbnail_url = absolute_media_url(request, content.thumbnail) or content.image_url
    stream_url = content.video_url
    youtube_embed_url = ""
    player_type = content.stream_type
    if content.stream_type == HomeContent.StreamType.YOUTUBE:
        youtube_embed_url = content.youtube_embed_url
        stream_url = ""
        player_type = "youtube"
    elif content.stream_type == HomeContent.StreamType.HLS:
        player_type = "hls"
    elif content.stream_type == HomeContent.StreamType.ACTION:
        player_type = "action"
    return {
        "id": content.pk,
        "section": content.section,
        "title": content.title,
        "subtitle": content.subtitle,
        "badge_text": content.badge_text,
        "thumbnail": thumbnail_url,
        "image_url": thumbnail_url,
        "stream_type": content.stream_type,
        "player_type": player_type,
        "video_url": stream_url,
        "stream_url": stream_url,
        "youtube_url": content.youtube_url,
        "youtube_embed_url": youtube_embed_url,
        "duration": content.duration,
        "viewers_count": content.viewers_count,
        "display_order": content.display_order,
    }


def serialize_home_utility(utility):
    return {
        "id": utility.pk,
        "title": utility.title,
        "subtitle": utility.subtitle,
        "icon": utility.icon,
        "action": utility.action,
        "display_order": utility.display_order,
    }


def serialize_app_menu(menu):
    return {
        "id": menu.pk,
        "title": menu.title,
        "slug": menu.slug,
        "target_type": menu.target_type,
        "target_value": menu.target_value,
        "display_order": menu.display_order,
    }


def serialize_app_home_setting(request, setting):
    return {
        "id": setting.pk,
        "title": setting.title,
        "subtitle": setting.subtitle,
        "hero_badge": setting.hero_badge,
        "hero_button_text": setting.hero_button_text,
        "logo": absolute_media_url(request, setting.logo),
        "updated_at": setting.updated_at.isoformat(),
    }


def serialize_home_district(city):
    return {
        "id": city.pk,
        "name": city.name,
        "slug": city.slug,
        "state": city.state.name if city.state_id else "",
        "state_id": city.state_id,
        "display_order": city.display_order,
    }


def serialize_empty_live_tv(request):
    setting = live_tv_setting()
    ticker_setting = news_ticker_setting()
    return {
        "id": None,
        "title": "",
        "description": "",
        "category": None,
        "category_id": None,
        "category_name": "",
        "state": None,
        "state_id": None,
        "state_name": "",
        "city": "",
        "headline": "",
        "lower_third_label": "",
        "ticker_label": ticker_setting.label or setting.default_ticker_label,
        "ticker_text": ticker_setting.text,
        "default_ticker_label": ticker_setting.label or setting.default_ticker_label,
        "default_ticker_text": ticker_setting.text,
        "ticker": ticker_items_from_text(ticker_setting.text),
        "player_type": "",
        "stream_url": "",
        "youtube_url": "",
        "youtube_embed_url": "",
        "poster_image": "",
        "channel_logo": absolute_media_url(request, setting.channel_logo),
        "is_live": False,
        "autoplay": False,
        "live_label": setting.live_label,
        "show_live_badge": False,
        "show_channel_logo": setting.show_channel_logo,
        "show_lower_third": False,
        "show_ticker": setting.show_ticker,
        "ticker_speed_seconds": ticker_setting.speed_seconds,
        "mobile_ticker_speed_seconds": ticker_setting.mobile_speed_seconds,
        "ticker_style": ticker_setting.style,
        "settings": serialize_live_tv_setting(request, setting),
        "web_url": "",
        "ads": mobile_live_tv_ads(),
        "detail": "No active live TV channel found.",
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


def shorts_request_user(request):
    if hasattr(request, "_shorts_request_user"):
        return request._shorts_request_user
    token_user = mobile_admin_user(request)
    if token_user:
        request._shorts_request_user = token_user
        return token_user
    if getattr(request, "user", None) and request.user.is_authenticated:
        request._shorts_request_user = request.user
        return request.user
    request._shorts_request_user = None
    return None


def mobile_admin_required(request):
    user = mobile_admin_user(request)
    if not user:
        return None, JsonResponse({"detail": "Admin login required."}, status=401)
    return user, None


def parse_required_location(post_data):
    raw_state_id = post_data.get("state_id", "").strip()
    raw_city_id = post_data.get("city_id", "").strip()
    errors = {}

    if not raw_state_id.isdigit():
        errors["state_id"] = ["State is required."]
    if not raw_city_id.isdigit():
        errors["city_id"] = ["City is required."]
    if errors:
        return None, None, errors

    state_id = int(raw_state_id)
    city_id = int(raw_city_id)
    if not LiveTVState.objects.filter(pk=state_id, is_active=True).exists():
        errors["state_id"] = ["Selected state is not active."]
    city = LiveTVCity.objects.filter(pk=city_id, state_id=state_id, is_active=True).first()
    if not city:
        errors["city_id"] = ["Selected city is required and must belong to selected state."]
    if errors:
        return None, None, errors
    return state_id, city_id, {}


def parse_optional_category(post_data):
    raw_category_id = post_data.get("category_id", "").strip()
    if raw_category_id.isdigit() and LiveTVCategory.objects.filter(pk=int(raw_category_id), is_active=True).exists():
        return int(raw_category_id)
    return None


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
            "auto_add_to_live": channel.auto_add_to_live,
            "auto_playlist_enabled": channel.auto_playlist_enabled,
            "loop_enabled": channel.loop_enabled,
            "duration_seconds": channel.effective_duration_seconds,
            "playlist_duration_seconds": channel.playlist_duration_seconds,
            "target_playlist_duration_seconds": channel.target_playlist_duration_seconds,
            "playlist_version": channel.playlist_version,
            "updated_at": channel.updated_at.isoformat(),
        }
    )
    return data


def serialize_shorts_video(request, short):
    user = shorts_request_user(request)
    setting = live_tv_setting()
    channel_user = short.created_by or get_user_model().objects.filter(is_superuser=True, is_active=True).order_by("id").first()
    channel_logo_url = absolute_media_url(request, setting.channel_logo)
    is_liked = bool(user and ShortsLike.objects.filter(short=short, user=user).exists())
    is_following = bool(
        user
        and channel_user
        and ChannelFollow.objects.filter(user=user, channel_user=channel_user).exists()
    )
    followers_count = ChannelFollow.objects.filter(channel_user=channel_user).count() if channel_user else 0
    comments = [
        {
            "id": comment.pk,
            "name": comment.name or "Viewer",
            "text": comment.text,
            "created_at": comment.created_at.isoformat(),
        }
        for comment in short.comments.all()[:5]
    ]
    hls_url = absolute_media_path_url(request, short.hls_master_url)
    fallback_video_url = absolute_media_url(request, short.video_file)
    video_url = hls_url or fallback_video_url
    return {
        "id": short.pk,
        "title": short.title,
        "headline": short.headline,
        "caption": short.caption,
        "location": short.location,
        "category": {"id": short.category_id, "name": short.category.name} if short.category_id else None,
        "category_id": short.category_id,
        "category_name": short.category.name if short.category_id else "",
        "state": {"id": short.state_id, "name": short.state.name} if short.state_id else None,
        "state_id": short.state_id,
        "state_name": short.state.name if short.state_id else "",
        "city": {"id": short.city_id, "name": short.city.name} if short.city_id else None,
        "city_id": short.city_id,
        "city_name": short.city.name if short.city_id else "",
        "location_name": short.location or (short.city.name if short.city_id else ""),
        "frame_template": short.frame_template,
        "video_url": video_url,
        "compressed_video_url": video_url,
        "mp4_url": fallback_video_url,
        "hls_url": hls_url,
        "thumbnail": absolute_media_url(request, short.thumbnail),
        "thumbnail_url": absolute_media_url(request, short.thumbnail),
        "processing_status": short.hls_status,
        "hls_status": short.hls_status,
        "processing_error": short.processing_error,
        "duration": short.duration,
        "is_published": short.is_published,
        "display_order": short.display_order,
        "likes_count": short.likes_count,
        "comments_count": short.comments_count,
        "shares_count": short.shares_count,
        "views_count": short.views_count,
        "likes": short.likes_count,
        "comments_total": short.comments_count,
        "shares": short.shares_count,
        "views": short.views_count,
        "is_liked": is_liked,
        "is_following": is_following,
        "channel_id": channel_user.pk if channel_user else None,
        "channel": {
            "id": channel_user.pk if channel_user else None,
            "name": "The UP Media",
            "logo_url": channel_logo_url,
            "is_verified": True,
            "is_following": is_following,
            "followers_count": followers_count,
        },
        "comments": comments,
        "created_at": short.created_at.isoformat(),
        "updated_at": short.updated_at.isoformat(),
    }


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


RENDER_TEMPLATE_ACCENTS = {
    "breaking-red": "#d71920",
    "live-report": "#e11d48",
    "classic-studio": "#b91c1c",
    "shorts-impact": "#ef4444",
    "sports-live": "#16a34a",
    "weather-alert": "#2563eb",
    "market-news": "#ca8a04",
    "festival-local": "#c2410c",
}


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
    ticker_label_text = job.ticker_label or "BREAKING NEWS"
    ticker_text = job.ticker_text or "The Up Media"
    title_text = job.title
    accent_color = RENDER_TEMPLATE_ACCENTS.get(job.frame_template, "#d71920")
    label_file = ffmpeg_text_file(label_text, "label")
    headline_file = ffmpeg_text_file(headline_text, "headline")
    ticker_label_file = ffmpeg_text_file(ticker_label_text, "ticker-label")
    ticker_file = ffmpeg_text_file("    |    ".join([ticker_text] * 3), "ticker")
    title_file = ffmpeg_text_file(title_text, "title")
    text_files.extend([label_file, headline_file, ticker_label_file, ticker_file, title_file])
    label_font_arg = ffmpeg_font_arg_for_text(label_text, devanagari_font, latin_font)
    headline_font_arg = ffmpeg_font_arg_for_text(headline_text, devanagari_font, latin_font)
    ticker_label_font_arg = ffmpeg_font_arg_for_text(ticker_label_text, devanagari_font, latin_font)
    ticker_font_arg = f":fontfile='{devanagari_font}'" if devanagari_font else ""
    title_font_arg = ffmpeg_font_arg_for_text(title_text, devanagari_font, latin_font)

    try:
        if job.render_format == "9:16":
            filter_complex = (
                "[0:v]scale=1080:607:force_original_aspect_ratio=increase,crop=1080:607,setsar=1[main];"
                "color=c=#08111f:s=1080x1920:d=999[bg];"
                "[bg][main]overlay=0:0[v0];"
                "[v0]drawbox=x=0:y=607:w=1080:h=72:color=white@0.94:t=fill,"
                f"drawbox=x=0:y=607:w=220:h=72:color={accent_color}@1:t=fill,"
                f"drawtext=textfile='{ffmpeg_path(label_file)}'{label_font_arg}:x=28:y=632:fontsize=32:fontcolor=white,"
                f"drawtext=textfile='{ffmpeg_path(headline_file)}'{headline_font_arg}:x=248:y=628:fontsize=34:fontcolor=#111827,"
                "drawbox=x=0:y=679:w=1080:h=54:color=#f8d24c@1:t=fill,"
                f"drawbox=x=0:y=679:w=250:h=54:color={accent_color}@1:t=fill,"
                f"drawtext=textfile='{ffmpeg_path(ticker_label_file)}'{ticker_label_font_arg}:x=28:y=695:fontsize=24:fontcolor=white,"
                f"drawtext=textfile='{ffmpeg_path(ticker_file)}'{ticker_font_arg}:x=250+w-mod(t*135\\,w+tw):y=694:fontsize=26:fontcolor=#111827,"
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
                f"drawbox=x=0:y=561:w=240:h=57:color={accent_color}@1:t=fill,"
                f"drawtext=textfile='{ffmpeg_path(label_file)}'{label_font_arg}:x=23:y=581:fontsize=28:fontcolor=white,"
                f"drawtext=textfile='{ffmpeg_path(headline_file)}'{headline_font_arg}:x=260:y=577:fontsize=31:fontcolor=#111827,"
                "drawbox=x=0:y=619:w=1280:h=39:color=#f8d24c@1:t=fill,"
                f"drawbox=x=0:y=619:w=210:h=39:color={accent_color}@1:t=fill,"
                f"drawtext=textfile='{ffmpeg_path(ticker_label_file)}'{ticker_label_font_arg}:x=18:y=630:fontsize=18:fontcolor=white,"
                f"drawtext=textfile='{ffmpeg_path(ticker_file)}'{ticker_font_arg}:x=210+w-mod(t*170\\,w+tw):y=630:fontsize=20:fontcolor=#111827,"
                "drawbox=x=0:y=657:w=1280:h=63:color=#08111f@0.96:t=fill,"
                f"drawtext=textfile='{ffmpeg_path(title_file)}'{title_font_arg}:x=28:y=676:fontsize=29:fontcolor=white,"
                "drawbox=x=1007:y=25:w=153:h=77:color=white@0.96:t=fill,"
                "drawtext=text='THE UP':x=1027:y=40:fontsize=24:fontcolor=#d71920,"
                "drawbox=x=1007:y=64:w=153:h=38:color=#08111f@1:t=fill,"
                "drawtext=text='MEDIA':x=1039:y=72:fontsize=23:fontcolor=white,"
                f"drawbox=x=25:y=25:w=100:h=40:color={accent_color}@1:t=fill,"
                "drawtext=text='LIVE':x=50:y=34:fontsize=23:fontcolor=white,"
                "format=yuv420p[vout]"
            )
        else:
            filter_complex = (
                "[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,setsar=1[main];"
                "[main]drawbox=x=0:y=842:w=1920:h=86:color=white@0.94:t=fill,"
                f"drawbox=x=0:y=842:w=360:h=86:color={accent_color}@1:t=fill,"
                f"drawtext=textfile='{ffmpeg_path(label_file)}'{label_font_arg}:x=34:y=872:fontsize=42:fontcolor=white,"
                f"drawtext=textfile='{ffmpeg_path(headline_file)}'{headline_font_arg}:x=390:y=866:fontsize=46:fontcolor=#111827,"
                "drawbox=x=0:y=928:w=1920:h=58:color=#f8d24c@1:t=fill,"
                f"drawbox=x=0:y=928:w=300:h=58:color={accent_color}@1:t=fill,"
                f"drawtext=textfile='{ffmpeg_path(ticker_label_file)}'{ticker_label_font_arg}:x=28:y=945:fontsize=27:fontcolor=white,"
                f"drawtext=textfile='{ffmpeg_path(ticker_file)}'{ticker_font_arg}:x=300+w-mod(t*220\\,w+tw):y=944:fontsize=30:fontcolor=#111827,"
                "drawbox=x=0:y=986:w=1920:h=94:color=#08111f@0.96:t=fill,"
                f"drawtext=textfile='{ffmpeg_path(title_file)}'{title_font_arg}:x=42:y=1014:fontsize=44:fontcolor=white,"
                "drawbox=x=1510:y=38:w=230:h=116:color=white@0.96:t=fill,"
                "drawtext=text='THE UP':x=1540:y=60:fontsize=36:fontcolor=#d71920,"
                "drawbox=x=1510:y=96:w=230:h=58:color=#08111f@1:t=fill,"
                "drawtext=text='MEDIA':x=1558:y=108:fontsize=34:fontcolor=white,"
                f"drawbox=x=38:y=38:w=150:h=60:color={accent_color}@1:t=fill,"
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
        "ticker_label": job.ticker_label,
        "ticker_text": job.ticker_text,
        "lower_third_label": job.lower_third_label,
        "render_format": job.render_format,
        "frame_category": job.frame_category,
        "frame_template": job.frame_template,
        "original_video_url": original_url,
        "rendered_video_url": rendered_url,
        "error": job.error_message,
        "created_at": job.created_at.isoformat(),
    }


def delete_file_field(file_field):
    if file_field:
        file_field.delete(save=False)


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


@never_cache
@require_GET
def current_live_api(request, slug=None):
    server_time = timezone.now()
    channels = LiveTVChannel.objects.filter(is_active=True).order_by("display_order", "pk")
    if slug:
        channel = get_object_or_404(channels, slug=slug)
    else:
        channel = get_main_live_channel(create=False) or channels.filter(is_live=True).first() or channels.first()

    if channel and channel.source_type == LiveTVChannel.SourceType.PLAYLIST and channel.auto_playlist_enabled:
        try:
            synced = serialize_synced_live_state(request, channel, server_time=server_time)
        except Exception:
            logger.exception("Current live playlist calculation failed for channel %s", channel.pk)
            synced = None
        if synced:
            return JsonResponse(synced)

    fallback_candidates = []
    if channel:
        fallback_candidates.append(channel)
    if not slug:
        fallback_candidates.extend(list(channels.exclude(pk=getattr(channel, "pk", None))))
    for fallback in fallback_candidates:
        if fallback.source_type == LiveTVChannel.SourceType.PLAYLIST:
            continue
        if fallback.player_source_type:
            return JsonResponse(serialize_live_fallback(request, fallback, server_time=server_time))

    data = serialize_empty_live_tv(request)
    data.update(
        {
            "is_live": False,
            "is_live_synced": False,
            "message": "अभी कोई लाइव प्रसारण उपलब्ध नहीं है",
            "server_time": server_time.isoformat(),
        }
    )
    return JsonResponse(data)


@require_GET
def current_live_tv_api(request):
    return current_live_api(request)


@require_GET
def app_home_api(request):
    channels = LiveTVChannel.objects.filter(is_active=True).select_related("category", "state", "city")
    active_channel = get_main_live_channel(create=False) or channels.filter(is_live=True).first() or channels.first()
    if active_channel and active_channel.source_type == LiveTVChannel.SourceType.PLAYLIST:
        main_live_tv = serialize_synced_live_state(request, active_channel) or serialize_empty_live_tv(request)
    else:
        main_live_tv = serialize_channel_for_mobile(request, active_channel) if active_channel else serialize_empty_live_tv(request)

    ticker_setting = news_ticker_setting()
    content = HomeContent.objects.filter(is_active=True)
    featured = content.filter(section=HomeContent.Section.FEATURED)[:12]
    top_videos = content.filter(section=HomeContent.Section.TOP_VIDEO)[:12]
    shorts = ShortsVideo.objects.filter(is_published=True).select_related("category", "state", "city").prefetch_related("comments")[:12]
    districts = LiveTVCity.objects.filter(is_active=True).select_related("state")[:30]

    data = {
        "success": True,
        "menu": [serialize_app_menu(menu) for menu in AppMenu.objects.filter(is_active=True)[:20]],
        "main_live_tv": main_live_tv,
        "ticker": {
            "label": ticker_setting.label,
            "text": ticker_setting.text,
            "items": ticker_items_from_text(ticker_setting.text),
            "speed_seconds": ticker_setting.speed_seconds,
            "mobile_speed_seconds": ticker_setting.mobile_speed_seconds,
            "style": ticker_setting.style,
        },
        "featured_content": [serialize_home_content(request, item) for item in featured],
        "shorts": [serialize_shorts_video(request, short) for short in shorts],
        "top_videos": [serialize_home_content(request, item) for item in top_videos],
        "utilities": [serialize_home_utility(utility) for utility in HomeUtility.objects.filter(is_active=True)[:12]],
        "districts": [serialize_home_district(city) for city in districts],
        "settings": serialize_app_home_setting(request, AppHomeSetting.get_solo()),
    }
    return JsonResponse(data)


@require_GET
def shorts_list_api(request):
    try:
        page = max(int(request.GET.get("page", "1")), 1)
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = min(max(int(request.GET.get("page_size", "12")), 1), 30)
    except (TypeError, ValueError):
        page_size = 12
    offset = (page - 1) * page_size
    shorts_qs = (
        ShortsVideo.objects.filter(is_published=True)
        .select_related("category", "state", "city", "created_by")
        .prefetch_related("comments")
    )
    total = shorts_qs.count()
    shorts = list(shorts_qs[offset : offset + page_size])
    results = [serialize_shorts_video(request, short) for short in shorts]
    return JsonResponse(
        {
            "count": total,
            "next": page + 1 if offset + page_size < total else None,
            "previous": page - 1 if page > 1 else None,
            "results": results,
            "shorts": results,
        }
    )


@csrf_exempt
@require_POST
def shorts_like_api(request, pk):
    user = shorts_request_user(request)
    if not user:
        return JsonResponse({"detail": "Login required."}, status=401)
    short = get_object_or_404(ShortsVideo, pk=pk, is_published=True)
    with transaction.atomic():
        like, created = ShortsLike.objects.get_or_create(short=short, user=user)
        if not created:
            like.delete()
        likes_count = ShortsLike.objects.filter(short=short).count()
        ShortsVideo.objects.filter(pk=short.pk).update(likes_count=likes_count)
    short.refresh_from_db(fields=["likes_count", "updated_at"])
    return JsonResponse({"id": short.pk, "is_liked": created, "likes_count": short.likes_count, "likes": short.likes_count})


@csrf_exempt
@require_POST
def shorts_follow_api(request, pk):
    user = shorts_request_user(request)
    if not user:
        return JsonResponse({"detail": "Login required."}, status=401)
    short = get_object_or_404(ShortsVideo.objects.select_related("created_by"), pk=pk, is_published=True)
    channel_user = short.created_by or get_user_model().objects.filter(is_superuser=True, is_active=True).order_by("id").first()
    if not channel_user:
        return JsonResponse({"detail": "Channel user not found."}, status=404)
    with transaction.atomic():
        follow, created = ChannelFollow.objects.get_or_create(user=user, channel_user=channel_user)
        if not created:
            follow.delete()
        followers_count = ChannelFollow.objects.filter(channel_user=channel_user).count()
    return JsonResponse(
        {
            "id": short.pk,
            "channel_id": channel_user.pk,
            "is_following": created,
            "followers_count": followers_count,
        }
    )


@csrf_exempt
@require_POST
def shorts_view_api(request, pk):
    short = get_object_or_404(ShortsVideo, pk=pk, is_published=True)
    session_key = f"shorts_viewed_{short.pk}"
    registered = not request.session.get(session_key)
    if registered:
        ShortsVideo.objects.filter(pk=short.pk).update(views_count=F("views_count") + 1)
        request.session[session_key] = True
        short.refresh_from_db(fields=["views_count", "updated_at"])
    return JsonResponse({"id": short.pk, "view_registered": registered, "views_count": short.views_count, "views": short.views_count})


@csrf_exempt
@require_POST
def shorts_share_api(request, pk):
    short = get_object_or_404(ShortsVideo, pk=pk, is_published=True)
    ShortsVideo.objects.filter(pk=short.pk).update(shares_count=F("shares_count") + 1)
    short.refresh_from_db(fields=["shares_count", "updated_at"])
    return JsonResponse({"id": short.pk, "shares_count": short.shares_count, "shares": short.shares_count})


@csrf_exempt
@require_POST
def shorts_comment_api(request, pk):
    short = get_object_or_404(ShortsVideo, pk=pk, is_published=True)
    text = request.POST.get("text", "").strip()
    if not text:
        return JsonResponse({"detail": "Comment text is required.", "errors": {"text": ["This field is required."]}}, status=400)
    name = request.POST.get("name", "").strip()[:80]
    comment = ShortsComment.objects.create(short=short, name=name, text=text[:1000])
    ShortsVideo.objects.filter(pk=short.pk).update(comments_count=F("comments_count") + 1)
    short.refresh_from_db(fields=["comments_count", "updated_at"])
    return JsonResponse(
        {
            "id": short.pk,
            "comments_count": short.comments_count,
            "comments_total": short.comments_count,
            "comment": {
                "id": comment.pk,
                "name": comment.name or "Viewer",
                "text": comment.text,
                "created_at": comment.created_at.isoformat(),
            },
        },
        status=201,
    )


@require_GET
def mobile_live_tv_meta_api(request):
    states = [
        {
            "id": state.pk,
            "name": state.name,
            "cities": [
                {"id": city.pk, "name": city.name}
                for city in state.cities.filter(is_active=True).order_by("display_order", "name")
            ],
        }
        for state in LiveTVState.objects.filter(is_active=True).order_by("display_order", "name")
    ]
    categories = [
        {"id": category.pk, "name": category.name}
        for category in LiveTVCategory.objects.filter(is_active=True).order_by("display_order", "name")
    ]
    return JsonResponse({
        "categories": categories,
        "states": states,
        "required_fields": {
            "video_upload": ["state_id", "city_id"],
            "shorts_upload": ["state_id", "city_id"],
        },
    })


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
    rendered_videos = manageable_render_jobs_for(user)[:50]
    media_downloads = manageable_media_downloads_for(user)[:50]
    settings_obj = live_tv_setting()
    main_channel = get_main_live_channel(create=False)
    playlist_state = calculate_current_playback(main_channel) if main_channel else None
    return JsonResponse(
        {
            "user": {"id": user.pk, "username": user.get_username(), "name": user.get_full_name() or user.get_username()},
            "settings": serialize_live_tv_setting(request, settings_obj),
            "facebook_live": serialize_facebook_live_setting(facebook_live_setting()),
            "channels": [serialize_channel_for_admin(request, channel) for channel in channels],
            "mobile_uploads": [],
            "rendered_videos": [serialize_render_job(request, job) for job in rendered_videos],
            "media_downloads": [serialize_media_download(request, job) for job in media_downloads],
            "source_types": list(LiveTVChannel.SourceType.values),
            "live_playlist": {
                "channel_id": main_channel.pk if main_channel else None,
                "active_items": main_channel.playlist_items.filter(is_active=True).count() if main_channel else 0,
                "total_duration_seconds": main_channel.playlist_duration_seconds if main_channel else 0,
                "target_duration_seconds": main_channel.target_playlist_duration_seconds if main_channel else 10800,
                "playlist_version": main_channel.playlist_version if main_channel else 0,
                "playback_started_at": main_channel.playback_started_at.isoformat() if main_channel and main_channel.playback_started_at else "",
                "loop_enabled": main_channel.loop_enabled if main_channel else True,
                "current_video_id": playlist_state["video"].pk if playlist_state else None,
                "current_seek_position": round(playlist_state["seek_position"], 3) if playlist_state else 0,
                "next_video_id": playlist_state["next_entry"].video_id if playlist_state and playlist_state.get("next_entry") else None,
                "processing_failures": LiveTVChannel.objects.filter(hls_status=LiveTVChannel.HLSStatus.FAILED, auto_add_to_live=True).count(),
            },
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
    ticker = news_ticker_setting()
    ticker.label = request.POST.get("default_ticker_label", ticker.label).strip()[:60] or ticker.label
    ticker.text = request.POST.get("default_ticker_text", ticker.text).strip() or ticker.text
    if "ticker_speed_seconds" in request.POST:
        try:
            ticker.speed_seconds = max(6, min(120, int(request.POST.get("ticker_speed_seconds") or ticker.speed_seconds)))
        except (TypeError, ValueError):
            pass
    if "mobile_ticker_speed_seconds" in request.POST:
        try:
            ticker.mobile_speed_seconds = max(6, min(120, int(request.POST.get("mobile_ticker_speed_seconds") or ticker.mobile_speed_seconds)))
        except (TypeError, ValueError):
            pass
    ticker.style = request.POST.get("ticker_style", ticker.style).strip()[:60] or ticker.style
    for field in ["show_live_badge", "show_channel_logo", "show_lower_third", "show_ticker", "autoplay"]:
        if field in request.POST:
            setattr(setting, field, request.POST.get(field) in {"1", "true", "on", "yes"})
    if request.FILES.get("channel_logo"):
        delete_file_field(setting.channel_logo)
        setting.channel_logo = request.FILES["channel_logo"]
    ticker.save()
    setting.save()
    return JsonResponse({"settings": serialize_live_tv_setting(request, setting)})

@csrf_exempt
@require_POST
def mobile_admin_channel_save_api(request):
    _user, error = mobile_admin_required(request)
    if error:
        return error

    channel_id = request.POST.get("id") or request.POST.get("channel_id")
    channel = LiveTVChannel.objects.filter(pk=channel_id).first() if channel_id else LiveTVChannel()

    video_file = request.FILES.get("video_file")
    source_type = request.POST.get("source_type", LiveTVChannel.SourceType.YOUTUBE).strip() or LiveTVChannel.SourceType.YOUTUBE
    if video_file:
        source_type = LiveTVChannel.SourceType.DIRECT
    youtube_url = request.POST.get("youtube_url", "").strip()
    stream_url = request.POST.get("stream_url", "").strip()

    if source_type == LiveTVChannel.SourceType.YOUTUBE and not youtube_url:
        return JsonResponse({"detail": "YouTube URL required.", "errors": {"youtube_url": ["This field is required."]}}, status=400)
    if source_type == LiveTVChannel.SourceType.DIRECT and not video_file and not channel.video_file:
        return JsonResponse({"detail": "Video file required.", "errors": {"video_file": ["This field is required."]}}, status=400)

    title = request.POST.get("title", "").strip()
    if not title:
        title = Path(getattr(video_file, "name", "")).stem if video_file else "The Up Media Live TV"

    channel.title = title[:180] or "The Up Media Live TV"
    channel.description = request.POST.get("description", "").strip()
    channel.source_type = source_type
    channel.auto_playlist_enabled = False
    channel.auto_add_to_live = source_type == LiveTVChannel.SourceType.DIRECT
    channel.youtube_url = youtube_url if source_type == LiveTVChannel.SourceType.YOUTUBE else ""
    channel.stream_url = stream_url if source_type == LiveTVChannel.SourceType.HLS else ""
    state_id, city_id, location_errors = parse_required_location(request.POST)
    if location_errors:
        return JsonResponse({"detail": "State and city are required.", "errors": location_errors}, status=400)
    channel.category_id = parse_optional_category(request.POST)
    channel.state_id = state_id
    channel.city_id = city_id
    if video_file:
        try:
            validate_uploaded_video(video_file)
        except Exception as exc:
            return JsonResponse({"detail": str(exc), "errors": {"video_file": [str(exc)]}}, status=400)
        delete_file_field(channel.video_file)
        channel.video_file = video_file
        channel.hls_master_url = ""
        channel.hls_status = LiveTVChannel.HLSStatus.PENDING
        channel.processing_error = ""
        channel.duration = None
    if request.FILES.get("poster_image"):
        delete_file_field(channel.poster_image)
        channel.poster_image = request.FILES["poster_image"]
    channel.is_active = True
    channel.is_live = True
    channel.lower_third_label = request.POST.get("lower_third_label", "").strip()[:60]
    channel.headline = request.POST.get("headline", "").strip()[:180]
    raw_display_order = request.POST.get("display_order")
    try:
        display_order = int(raw_display_order) if raw_display_order not in (None, "") else None
    except (TypeError, ValueError):
        display_order = None
    if display_order is None or display_order < 0 or display_order > 2147483647:
        if channel.pk and channel.display_order is not None:
            display_order = channel.display_order
        else:
            last_channel = LiveTVChannel.objects.order_by("-display_order").first()
            display_order = (last_channel.display_order + 1) if last_channel else 0
    channel.display_order = display_order
    channel.meta_title = request.POST.get("meta_title", "").strip()[:160]
    channel.meta_description = request.POST.get("meta_description", "").strip()[:220]
    channel.save()
    if channel.source_type == LiveTVChannel.SourceType.DIRECT and channel.video_file:
        enqueue_live_channel_hls_job(channel.pk)
    return JsonResponse({"channel": serialize_channel_for_admin(request, channel)})


@csrf_exempt
@require_POST
def mobile_admin_channel_delete_api(request, pk):
    _user, error = mobile_admin_required(request)
    if error:
        return error

    channel = get_object_or_404(LiveTVChannel, pk=pk)
    try:
        channel.delete()
    except ProtectedError:
        return JsonResponse({"detail": "Video active ya historical live playlist me use ho rahi hai; pehle playlist se remove kare."}, status=409)
    return JsonResponse({"ok": True})


@csrf_exempt
@require_POST
def mobile_admin_shorts_upload_api(request):
    user, error = mobile_admin_required(request)
    if error:
        return error

    video_file = request.FILES.get("video_file")
    if not video_file:
        return JsonResponse({"detail": "Shorts video file required.", "errors": {"video_file": ["This field is required."]}}, status=400)
    try:
        validate_uploaded_video(video_file)
    except Exception as exc:
        return JsonResponse({"detail": str(exc), "errors": {"video_file": [str(exc)]}}, status=400)

    title = request.POST.get("title", "").strip()
    headline = request.POST.get("headline", "").strip()
    caption = request.POST.get("caption", "").strip()
    location = request.POST.get("location", "").strip()
    state_id, city_id, location_errors = parse_required_location(request.POST)
    if location_errors:
        return JsonResponse({"detail": "State and city are required.", "errors": location_errors}, status=400)
    category_id = parse_optional_category(request.POST)
    frame_template = request.POST.get("frame_template", "").strip() or "normal_black_red"
    raw_display_order = request.POST.get("display_order")
    try:
        display_order = int(raw_display_order) if raw_display_order not in (None, "") else None
    except (TypeError, ValueError):
        display_order = None
    if display_order is None or display_order < 0 or display_order > 2147483647:
        last_short = ShortsVideo.objects.order_by("-display_order").first()
        display_order = (last_short.display_order + 1) if last_short else 0

    short = ShortsVideo.objects.create(
        title=title[:180],
        headline=headline[:180],
        caption=caption,
        location=location[:120],
        category_id=category_id,
        state_id=state_id,
        city_id=city_id,
        frame_template=frame_template[:60],
        video_file=video_file,
        thumbnail=request.FILES.get("thumbnail"),
        is_published=True,
        display_order=display_order,
        created_by=user,
    )
    if not short.original_video:
        short.original_video.name = short.video_file.name
        short.save(update_fields=["original_video", "updated_at"])
    enqueue_short_hls_job(short.pk)
    return JsonResponse({"short": serialize_shorts_video(request, short)}, status=201)


@csrf_exempt
@require_POST
def mobile_admin_rendered_video_update_api(request, pk):
    user, error = mobile_admin_required(request)
    if error:
        return error

    job = get_object_or_404(manageable_render_jobs_for(user), pk=pk)
    title = request.POST.get("title", "").strip()
    headline = request.POST.get("headline", "").strip()
    ticker_label = request.POST.get("ticker_label", "").strip()
    ticker_text = request.POST.get("ticker_text", "").strip()
    lower_third_label = request.POST.get("lower_third_label", "").strip()
    if title:
        job.title = title[:180]
    job.headline = headline[:180]
    if ticker_label:
        job.ticker_label = ticker_label[:60]
    job.ticker_text = ticker_text[:260]
    if lower_third_label:
        job.lower_third_label = lower_third_label[:60]
    job.save(update_fields=["title", "headline", "ticker_label", "ticker_text", "lower_third_label", "updated_at"])
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
    ticker_setting = news_ticker_setting()
    ticker_label = request.POST.get("ticker_label", "").strip() or ticker_setting.label or "BREAKING NEWS"
    ticker_text = request.POST.get("ticker_text", "").strip() or ticker_setting.text or "The Up Media"
    lower_third_label = request.POST.get("lower_third_label", "").strip() or (active_channel.lower_third_label if active_channel else "BREAKING NEWS")
    render_format = request.POST.get("render_format", "16:9").strip()
    if render_format not in {"fast_720p", "16:9", "9:16"}:
        render_format = "16:9"
    frame_category = request.POST.get("frame_category", "").strip()
    frame_template = request.POST.get("frame_template", "").strip()

    job = SocialRenderedVideo.objects.create(
        title=title[:180],
        headline=headline[:180],
        ticker_label=ticker_label[:60],
        ticker_text=ticker_text[:260],
        lower_third_label=lower_third_label[:60],
        render_format=render_format,
        frame_category=frame_category[:40],
        frame_template=frame_template[:60],
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
            if channel.source_type == LiveTVChannel.SourceType.DIRECT and channel.video_file and channel.hls_status != LiveTVChannel.HLSStatus.COMPLETED:
                enqueue_live_channel_hls_job(channel.pk)
            messages.success(request, "Live TV channel saved.")
            return redirect(f"{request.path}?edit={channel.pk}")
    else:
        form = LiveTVChannelForm(instance=instance)

    main_playlist_channel = get_main_live_channel(create=False)
    playlist_state = calculate_current_playback(main_playlist_channel) if main_playlist_channel else None
    playlist_items = (
        main_playlist_channel.playlist_items.select_related("video").order_by("position", "pk")
        if main_playlist_channel
        else LiveTVPlaylistItem.objects.none()
    )
    preview_channel = instance or main_playlist_channel or channels.first()
    return render(
        request,
        "live_tv/dashboard.html",
        {
            "channels": channels,
            "form": form,
            "selected_channel": instance,
            "preview_channel": preview_channel,
            "news_ticker": news_ticker_setting(),
            "main_playlist_channel": main_playlist_channel,
            "playlist_state": playlist_state,
            "playlist_items": playlist_items,
        },
    )


@superuser_required
@require_POST
def delete_channel(request, pk):
    channel = get_object_or_404(LiveTVChannel, pk=pk)
    try:
        channel.delete()
        messages.success(request, "Live TV channel deleted.")
    except ProtectedError:
        messages.error(request, "Channel playlist history me use ho raha hai; playlist references remove kiye bina delete nahi hoga.")
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
