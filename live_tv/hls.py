import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.utils import timezone

from .models import ShortsVideo
from .models import LiveTVChannel

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
except ImportError:  # pragma: no cover
    Image = ImageDraw = ImageFont = ImageOps = None


logger = logging.getLogger(__name__)


ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
ALLOWED_VIDEO_MIME_PREFIXES = ("video/",)
HLS_VARIANTS = (
    {"name": "360p", "short": 360, "video_bitrate": "650k", "audio_bitrate": "64k", "bandwidth": 800000},
    {"name": "480p", "short": 480, "video_bitrate": "1100k", "audio_bitrate": "96k", "bandwidth": 1300000},
    {"name": "720p", "short": 720, "video_bitrate": "2200k", "audio_bitrate": "128k", "bandwidth": 2600000},
)
SHORTS_RENDER_WIDTH = 1080
SHORTS_RENDER_HEIGHT = 1920


class HLSProcessingError(Exception):
    pass


def validate_uploaded_video(file_obj):
    name = getattr(file_obj, "name", "") or ""
    suffix = Path(name).suffix.lower()
    if suffix not in ALLOWED_VIDEO_EXTENSIONS:
        raise HLSProcessingError("Only MP4, MOV, M4V, WEBM and MKV video files are allowed.")
    content_type = getattr(file_obj, "content_type", "") or ""
    if content_type and not content_type.startswith(ALLOWED_VIDEO_MIME_PREFIXES):
        raise HLSProcessingError("Uploaded file is not a valid video.")


def ffmpeg_binary():
    return getattr(settings, "FFMPEG_BINARY", "ffmpeg")


def ffprobe_binary():
    return getattr(settings, "FFPROBE_BINARY", "ffprobe")


def run_command(args, timeout=1800):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, shell=False)
    if result.returncode != 0:
        error = (result.stderr or result.stdout or "FFmpeg command failed.").strip()
        raise HLSProcessingError(error[-3000:])
    return result


def parse_ffmpeg_time(line):
    match = re.search(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)", line or "")
    if not match:
        return None
    hours, minutes, seconds = match.groups()
    return (int(hours) * 3600) + (int(minutes) * 60) + float(seconds)


def progress_updater(model_cls, object_id, field_name="hls_progress_percent"):
    last_percent = {"value": -1}

    def update(percent):
        safe_percent = max(0, min(99, int(percent)))
        if safe_percent <= last_percent["value"]:
            return
        last_percent["value"] = safe_percent
        model_cls.objects.filter(pk=object_id).update(**{field_name: safe_percent, "updated_at": timezone.now()})

    return update


def run_ffmpeg_command(args, duration=0, progress_callback=None, timeout=1800):
    progress_args = list(args)
    if progress_args and "ffmpeg" in Path(progress_args[0]).name.lower() and "-progress" not in progress_args:
        progress_args[1:1] = ["-nostats", "-progress", "pipe:1"]
    process = subprocess.Popen(progress_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    output_tail = []
    try:
        for line in process.stdout:
            output_tail.append(line)
            output_tail = output_tail[-40:]
            current_time = None
            if line.startswith("out_time_ms="):
                try:
                    current_time = int(line.split("=", 1)[1].strip()) / 1000000
                except (TypeError, ValueError):
                    current_time = None
            elif line.startswith("out_time="):
                current_time = parse_ffmpeg_time("time=" + line.split("=", 1)[1].strip())
            else:
                current_time = parse_ffmpeg_time(line)
            if progress_callback and current_time is not None and duration:
                progress_callback(min(99, (current_time / duration) * 100))
        return_code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        raise HLSProcessingError("FFmpeg command timed out.") from exc

    if return_code != 0:
        error = ("".join(output_tail) or "FFmpeg command failed.").strip()
        raise HLSProcessingError(error[-3000:])

def probe_video(input_path):
    result = run_command(
        [
            ffprobe_binary(),
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            str(input_path),
        ],
        timeout=60,
    )
    data = json.loads(result.stdout or "{}")
    streams = data.get("streams") or []
    video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    audio_stream = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    if not video_stream:
        raise HLSProcessingError("No video stream found.")
    duration = data.get("format", {}).get("duration") or video_stream.get("duration")
    return {
        "width": int(video_stream.get("width") or 0),
        "height": int(video_stream.get("height") or 0),
        "duration": float(duration) if duration else None,
        "has_audio": audio_stream is not None,
    }


def scale_filter(metadata, short_side):
    width = metadata.get("width") or 0
    height = metadata.get("height") or 0
    if width >= height:
        scale = f"scale=-2:{short_side}:force_original_aspect_ratio=decrease"
    else:
        scale = f"scale={short_side}:-2:force_original_aspect_ratio=decrease"
    return f"{scale},scale=trunc(iw/2)*2:trunc(ih/2)*2"


def write_master_playlist(output_dir, metadata):
    lines = ["#EXTM3U", "#EXT-X-VERSION:3"]
    landscape = (metadata.get("width") or 0) >= (metadata.get("height") or 0)
    for variant in HLS_VARIANTS:
        short = variant["short"]
        resolution = f"{int(short * 16 / 9)}x{short}" if landscape else f"{short}x{int(short * 16 / 9)}"
        lines.append(
            f"#EXT-X-STREAM-INF:BANDWIDTH={variant['bandwidth']},RESOLUTION={resolution},CODECS=\"avc1.42e01e,mp4a.40.2\""
        )
        lines.append(f"{variant['name']}/index.m3u8")
    (output_dir / "master.m3u8").write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_public_media_tree(path):
    for item in path.rglob("*"):
        try:
            if item.is_dir():
                item.chmod(0o755)
            else:
                item.chmod(0o644)
        except (OSError, PermissionError):
            # Files are already readable under the service umask. A transient
            # chmod failure (for example an antivirus/open-file lock) must not
            # discard an otherwise complete HLS conversion.
            logger.warning("Could not normalize media permissions for %s.", item, exc_info=True)
    try:
        path.chmod(0o755)
    except (OSError, PermissionError):
        logger.warning("Could not normalize media directory permissions for %s.", path, exc_info=True)


def hls_media_file_exists(media_path):
    return bool(media_path and (Path(settings.MEDIA_ROOT) / media_path).exists())


def restore_existing_hls_completion(instance):
    """Trust an atomically published HLS tree over a stale database status."""
    if not instance or not instance.pk or not instance.hls_master_url:
        return False
    if not hls_media_file_exists(instance.hls_master_url):
        return False
    model = type(instance)
    updates = {}
    if instance.hls_status != model.HLSStatus.COMPLETED:
        updates["hls_status"] = model.HLSStatus.COMPLETED
    if instance.hls_progress_percent != 100:
        updates["hls_progress_percent"] = 100
    if instance.processing_error:
        updates["processing_error"] = ""
    if updates:
        updates["updated_at"] = timezone.now()
        model.objects.filter(pk=instance.pk).update(**updates)
        for field, value in updates.items():
            setattr(instance, field, value)
    return True


def acquire_hls_enqueue_lock(kind, object_id, stale_seconds=120):
    lock_dir = Path(settings.MEDIA_ROOT) / "live-tv" / "hls" / ".queue-locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / f"{kind}-{object_id}.lock"
    try:
        if lock_path.exists() and (timezone.now().timestamp() - lock_path.stat().st_mtime) > stale_seconds:
            lock_path.unlink(missing_ok=True)
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode("ascii", errors="ignore"))
        os.close(fd)
        return lock_path
    except FileExistsError:
        return None


def release_hls_enqueue_lock(kind, object_id):
    lock_path = Path(settings.MEDIA_ROOT) / "live-tv" / "hls" / ".queue-locks" / f"{kind}-{object_id}.lock"
    lock_path.unlink(missing_ok=True)


def hls_processing_lock_is_active(name):
    lock_path = Path(settings.MEDIA_ROOT) / "live-tv" / "hls" / ".locks" / f"{name}.lock"
    if not lock_path.exists():
        return False
    stale_seconds = int(getattr(settings, "LIVE_TV_HLS_PROCESSING_STALE_MINUTES", 20)) * 60
    try:
        return (timezone.now().timestamp() - lock_path.stat().st_mtime) <= stale_seconds
    except OSError:
        return False


def acquire_hls_processing_lock(name):
    lock_dir = Path(settings.MEDIA_ROOT) / "live-tv" / "hls" / ".locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / f"{name}.lock"
    stale_seconds = int(getattr(settings, "LIVE_TV_HLS_PROCESSING_STALE_MINUTES", 20)) * 60
    try:
        if lock_path.exists() and (timezone.now().timestamp() - lock_path.stat().st_mtime) > stale_seconds:
            lock_path.unlink(missing_ok=True)
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode("ascii", errors="ignore"))
        return fd, lock_path
    except FileExistsError:
        return None, lock_path


def release_hls_processing_lock(fd, lock_path):
    if fd is not None:
        try:
            os.close(fd)
        except OSError:
            pass
    if lock_path:
        try:
            lock_path.unlink(missing_ok=True)
        except OSError:
            pass


def ffmpeg_escape(text):
    return " ".join((text or "").split()).replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:")


def safe_hex_color(value, fallback):
    value = (value or "").strip()
    return value if re.fullmatch(r"#[0-9a-fA-F]{6}", value) else fallback


def shorts_font_path():
    candidates = [
        getattr(settings, "FFMPEG_FONT_FILE", ""),
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansDevanagariUI-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSerifDevanagari-Bold.ttf",
        "/usr/share/fonts/truetype/lohit-devanagari/Lohit-Devanagari.ttf",
        "C:/Windows/Fonts/NirmalaB.ttf",
        "C:/Windows/Fonts/Nirmala.ttf",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate).replace("\\", "/")
    return ""


def shorts_latin_font_path():
    candidates = [
        getattr(settings, "FFMPEG_LATIN_FONT_FILE", ""),
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate).replace("\\", "/")
    return shorts_font_path()


def shorts_font_arg():
    font_path = shorts_font_path()
    ffmpeg_font = font_path.replace(":", "\\:")
    return f":fontfile='{ffmpeg_font}'" if ffmpeg_font else ":font='Arial'"


def shorts_image_font(size):
    if ImageFont is None:
        return None
    font_path = shorts_font_path()
    try:
        if font_path:
            return ImageFont.truetype(font_path, size=size, layout_engine=ImageFont.Layout.RAQM)
    except Exception:
        logger.exception("Could not load shorts font %s.", font_path)
    return ImageFont.load_default()


def shorts_latin_image_font(size):
    if ImageFont is None:
        return None
    font_path = shorts_latin_font_path()
    try:
        if font_path:
            return ImageFont.truetype(font_path, size=size)
    except Exception:
        logger.exception("Could not load shorts latin font %s.", font_path)
    return ImageFont.load_default()


def wrap_text_lines(text, max_chars=18, max_lines=3):
    words = " ".join((text or "").split()).split()
    lines = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > max_chars:
            lines.append(current)
            current = word
            if len(lines) >= max_lines:
                break
        else:
            current = candidate
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) == max_lines and len(words) > len(" ".join(lines).split()):
        lines[-1] = f"{lines[-1].rstrip('!.।')[:max_chars - 1]}..."
    return lines or [text or "The Up Media"]


def wrap_text_pixels(draw, text, font, max_width, max_lines=3):
    words = " ".join((text or "").split()).split()
    lines = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if current and (bbox[2] - bbox[0]) > max_width:
            lines.append(current)
            current = word
            if len(lines) >= max_lines:
                break
        else:
            current = candidate
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) == max_lines and len(words) > len(" ".join(lines).split()):
        line = lines[-1].rstrip("!.।")
        while line and (draw.textbbox((0, 0), f"{line}...", font=font)[2] > max_width):
            line = line[:-1].rstrip()
        lines[-1] = f"{line}..." if line else "..."
    return lines or [text or "The Up Media"]


def draw_centered_text(draw, box, text, font, fill):
    left, top, right, bottom = box
    bbox = draw.textbbox((0, 0), text, font=font)
    x = left + ((right - left) - (bbox[2] - bbox[0])) / 2
    y = top + ((bottom - top) - (bbox[3] - bbox[1])) / 2 - bbox[1]
    draw.text((x, y), text, font=font, fill=fill)


def shorts_brand_name(short):
    if short.channel_name:
        return short.channel_name
    try:
        from .models import LiveTVSetting

        return LiveTVSetting.get_solo().name or "The Up Media"
    except Exception:
        return "The Up Media"


def shorts_logo_path(short):
    if short.channel_logo:
        return Path(short.channel_logo.path)
    try:
        from .models import LiveTVSetting

        setting = LiveTVSetting.get_solo()
        if setting.channel_logo:
            return Path(setting.channel_logo.path)
    except Exception:
        logger.exception("Could not load default shorts logo.")
    return None


def make_short_logo_badge(source_path, output_path, size=128):
    if not source_path or not Path(source_path).exists() or Image is None:
        return None
    try:
        badge_size = int(size)
        border = 4
        inner = badge_size - (border * 2)
        badge = Image.new("RGBA", (badge_size, badge_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(badge)
        draw.ellipse((0, 0, badge_size - 1, badge_size - 1), fill=(255, 255, 255, 245))
        draw.ellipse((border, border, badge_size - border - 1, badge_size - border - 1), fill=(220, 24, 24, 255))
        logo = Image.open(source_path).convert("RGBA")
        alpha_bbox = logo.getchannel("A").getbbox()
        if alpha_bbox:
            logo = logo.crop(alpha_bbox)
        logo = ImageOps.fit(
            logo,
            (inner, inner),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
        canvas = Image.new("RGBA", (inner, inner), (255, 255, 255, 0))
        canvas.alpha_composite(logo, (0, 0))
        mask = Image.new("L", (inner, inner), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, inner - 1, inner - 1), fill=255)
        badge.alpha_composite(ImageOps.fit(canvas, (inner, inner), method=Image.Resampling.LANCZOS), (border, border))
        badge.putalpha(Image.composite(badge.getchannel("A"), Image.new("L", (badge_size, badge_size), 0), Image.new("L", (badge_size, badge_size), 255)))
        badge.save(output_path)
        return output_path
    except Exception:
        logger.exception("Could not create shorts logo badge.")
        return source_path


def create_short_frame_images(short, metadata, bg_path, fg_path, logo_path=None):
    if Image is None:
        return False
    template = short.frame_template or "normal_black_red"
    template_styles = {
        "normal_black_red": {"background": "#070707", "panel": "#0d0d0d", "accent": "#ef1717", "text": "#ffffff", "highlight": "#f8d24c"},
        "normal_white_blue": {"background": "#eef3fb", "panel": "#ffffff", "accent": "#1d4ed8", "text": "#111111", "highlight": "#1d4ed8"},
        "normal_storm_yellow": {"background": "#080c14", "panel": "#111827", "accent": "#f59e0b", "text": "#ffffff", "highlight": "#f8d24c"},
        "normal_white_red": {"background": "#f8fafc", "panel": "#ffffff", "accent": "#ef1717", "text": "#111111", "highlight": "#ef1717"},
        "breaking_big": {"background": "#110204", "panel": "#ffffff", "accent": "#ef1717", "text": "#ffffff", "highlight": "#ffffff"},
        "hindu_dharmik": {"background": "#210800", "panel": "#431300", "accent": "#f59e0b", "text": "#ffffff", "highlight": "#fde68a"},
    }
    style = template_styles.get(template, template_styles["normal_black_red"])
    primary = safe_hex_color(style["accent"], "#d71920")
    secondary = safe_hex_color(short.frame_secondary_color, "#2b0508")
    background = safe_hex_color(style["background"], "#050505")
    text_color = safe_hex_color(style["text"], "#ffffff")
    highlight_color = safe_hex_color(style["highlight"], primary)
    headline = short.headline or short.title
    bg = Image.new("RGBA", (SHORTS_RENDER_WIDTH, SHORTS_RENDER_HEIGHT), background)
    fg = Image.new("RGBA", (SHORTS_RENDER_WIDTH, SHORTS_RENDER_HEIGHT), (0, 0, 0, 0))
    bg_draw = ImageDraw.Draw(bg)
    fg_draw = ImageDraw.Draw(fg)

    bg_draw.rectangle((0, 0, SHORTS_RENDER_WIDTH, SHORTS_RENDER_HEIGHT), fill=background)
    if template in {"normal_black_red", "normal_storm_yellow", "breaking_big", "hindu_dharmik"}:
        for step in range(0, 420, 3):
            ratio = step / 420
            if template == "hindu_dharmik":
                color = (int(33 + (165 * ratio)), int(8 + (75 * ratio)), int(11 * ratio), 255)
            elif template == "normal_storm_yellow":
                color = (int(7 + (18 * ratio)), int(10 + (12 * ratio)), 14, 255)
            else:
                color = (int(18 + (88 * ratio)), int(3 + (12 * ratio)), 14, 255)
            bg_draw.rectangle((0, step, SHORTS_RENDER_WIDTH, step + 3), fill=color)
    else:
        bg_draw.rectangle((0, 0, SHORTS_RENDER_WIDTH, 420), fill=background)

    headline_font = shorts_image_font(68 if template == "breaking_big" else 64)
    headline_lines = wrap_text_pixels(fg_draw, headline, headline_font, 900, max_lines=3)
    y = 78
    if template == "breaking_big":
        fg_draw.rounded_rectangle((38, 42, 490, 118), radius=12, fill=primary)
        fg_draw.text((62, 50), "BIG BREAKING", font=shorts_latin_image_font(43), fill="#ffffff")
        y = 140
    elif template == "hindu_dharmik":
        fg_draw.rounded_rectangle((38, 42, 520, 118), radius=12, fill=primary)
        fg_draw.text((62, 50), "ॐ  धर्म • संस्कृति", font=shorts_image_font(38), fill="#ffffff")
        y = 140
    for index, line in enumerate(headline_lines):
        bbox = fg_draw.textbbox((0, 0), line, font=headline_font, stroke_width=3)
        line_width = bbox[2] - bbox[0]
        x = max(60, int((SHORTS_RENDER_WIDTH - line_width) / 2))
        line_color = highlight_color if index == len(headline_lines) - 1 and template != "breaking_big" else text_color
        fg_draw.text((x, y), line, font=headline_font, fill=line_color, stroke_width=2, stroke_fill=(0, 0, 0, 120))
        y += 74

    video_outer = (18, 370, 1062, 1864)
    video_inner = (36, 388, 1044, 1846)
    fg_draw.rounded_rectangle((10, 362, 1070, 1872), radius=34, outline=(0, 0, 0, 110), width=14)
    fg_draw.rounded_rectangle((14, 366, 1066, 1868), radius=32, outline=(255, 42, 48, 95), width=9)
    fg_draw.rounded_rectangle(video_outer, radius=30, outline=(118, 0, 0, 255), width=22)
    fg_draw.rounded_rectangle(video_outer, radius=30, outline=primary, width=15)
    fg_draw.rounded_rectangle((27, 379, 1053, 1855), radius=27, outline=(255, 72, 72, 180), width=4)
    fg_draw.rounded_rectangle(video_inner, radius=24, outline=(255, 255, 255, 250), width=6)
    fg_draw.line((52, 397, 1028, 397), fill=(255, 255, 255, 135), width=3)
    fg_draw.line((52, 1837, 1028, 1837), fill=(255, 255, 255, 95), width=2)

    badge = None
    if logo_path and Path(logo_path).exists():
        badge = make_short_logo_badge(logo_path, Path(fg_path).with_name("short-logo-badge.png"), size=170)
    if badge and Path(badge).exists():
        logo = Image.open(badge).convert("RGBA")
        fg.alpha_composite(logo, (455, 285))
    else:
        fg_draw.ellipse((455, 285, 625, 455), fill=primary, outline=(255, 255, 255, 220), width=5)
        draw_centered_text(fg_draw, (455, 285, 625, 455), "UP", shorts_latin_image_font(46), text_color)

    bg.convert("RGB").save(bg_path)
    fg.save(fg_path)
    return True


def shorts_frame_filter(short, metadata, with_logo=False):
    primary = safe_hex_color(short.frame_primary_color, "#d71920")
    secondary = safe_hex_color(short.frame_secondary_color, "#2b0508")
    background = safe_hex_color(short.frame_background_color, "#050505")
    text_color = safe_hex_color(short.frame_text_color, "#ffffff")
    font_arg = shorts_font_arg()
    headline_lines = wrap_text_lines(short.headline or short.title, max_chars=18, max_lines=3)
    headline_draws = []
    for index, line in enumerate(headline_lines):
        headline_draws.append(
            f"drawtext=text='{ffmpeg_escape(line)}':x=(w-text_w)/2:y={66 + (index * 74)}:fontsize=64:fontcolor={text_color}{font_arg}:borderw=3:bordercolor=black@0.55"
        )
    headline_filter = ",".join(headline_draws)
    channel = ffmpeg_escape(shorts_brand_name(short))
    if short.video_fit == ShortsVideo.VideoFit.COVER:
        video_scale = "scale=1008:1458:force_original_aspect_ratio=increase,crop=1008:1458"
    else:
        video_scale = "scale=1008:1458:force_original_aspect_ratio=increase,crop=1008:1458"
    graph = (
        f"color=c={background}:s={SHORTS_RENDER_WIDTH}x{SHORTS_RENDER_HEIGHT}:d={metadata.get('duration') or 1}[bg];"
        f"[0:v]{video_scale},setsar=1[v0];"
        f"[bg]drawbox=x=0:y=0:w=1080:h=120:color=#170303@1:t=fill,"
        f"drawbox=x=0:y=120:w=1080:h=300:color=#6b0c0e@1:t=fill,"
        f"drawbox=x=0:y=260:w=1080:h=160:color={primary}@0.58:t=fill,"
        f"{headline_filter}[card];"
        f"[card][v0]overlay=x=36:y=388:shortest=1,"
        f"drawbox=x=10:y=362:w=1060:h=1510:color=black@0.45:t=14,"
        f"drawbox=x=14:y=366:w=1052:h=1502:color=#ff2a30@0.38:t=9,"
        f"drawbox=x=18:y=370:w=1044:h=1494:color=#760000@1:t=22,"
        f"drawbox=x=18:y=370:w=1044:h=1494:color={primary}@1:t=15,"
        f"drawbox=x=27:y=379:w=1026:h=1476:color=#ff4848@0.70:t=4,"
        f"drawbox=x=36:y=388:w=1008:h=1458:color=white@0.98:t=6,"
        f"drawbox=x=52:y=397:w=976:h=3:color=white@0.52:t=fill,"
        f"drawbox=x=52:y=1837:w=976:h=2:color=white@0.38:t=fill[base]"
    )
    if with_logo:
        graph += ";[1:v]scale=170:170:force_original_aspect_ratio=increase,crop=170:170,format=rgba[logo];[base][logo]overlay=x=455:y=285:shortest=1[outv]"
    else:
        graph += f";[base]drawbox=x=455:y=285:w=170:h=170:color={primary}@1:t=fill,drawtext=text='{channel}':x=480:y=350:fontsize=28:fontcolor=white{font_arg}[outv]"
    return graph


def generate_short_thumbnail(short, input_path):
    thumb_dir = Path(settings.MEDIA_ROOT) / "shorts" / "thumbnails" / str(short.pk)
    thumb_dir.mkdir(parents=True, exist_ok=True)
    tmp_thumb_path = thumb_dir / f"short-{short.pk}.tmp.jpg"
    run_command(
        [
            ffmpeg_binary(),
            "-y",
            "-ss",
            "00:00:00.300",
            "-i",
            str(input_path),
            "-frames:v",
            "1",
            "-update",
            "1",
            "-f",
            "image2",
            "-q:v",
            "3",
            str(tmp_thumb_path),
        ],
        timeout=60,
    )
    if not tmp_thumb_path.exists():
        raise HLSProcessingError("Thumbnail frame was not created.")
    with tmp_thumb_path.open("rb") as handle:
        short.thumbnail.save(f"short-{short.pk}.jpg", File(handle), save=True)
    tmp_thumb_path.unlink(missing_ok=True)


def render_short_frame(short_id):
    short = ShortsVideo.objects.select_related("city").get(pk=short_id)
    source_file = short.original_video or short.video_file
    if not source_file:
        raise HLSProcessingError("Short has no raw video file.")
    input_path = Path(source_file.path)
    if not input_path.exists():
        raise HLSProcessingError("Raw shorts video file not found.")

    ShortsVideo.objects.filter(pk=short.pk).update(hls_status=ShortsVideo.HLSStatus.PROCESSING, hls_progress_percent=1, processing_error="", updated_at=timezone.now())
    metadata = probe_video(input_path)
    output_dir = Path(settings.MEDIA_ROOT) / "shorts" / "rendered" / str(short.pk)
    output_dir.mkdir(parents=True, exist_ok=True)
    tmp_output = output_dir / f"short-{short.pk}.tmp.mp4"
    final_output = output_dir / f"short-{short.pk}.mp4"
    logo_path = shorts_logo_path(short)
    bg_path = output_dir / f"short-{short.pk}-frame-bg.png"
    fg_path = output_dir / f"short-{short.pk}-frame-fg.png"
    use_template = create_short_frame_images(short, metadata, bg_path, fg_path, logo_path=logo_path)
    if use_template:
        video_scale = "scale=1008:1458:force_original_aspect_ratio=increase,crop=1008:1458,setsar=1"
        args = [
            ffmpeg_binary(),
            "-y",
            "-loop",
            "1",
            "-t",
            str(metadata.get("duration") or 1),
            "-i",
            str(bg_path),
            "-i",
            str(input_path),
            "-loop",
            "1",
            "-t",
            str(metadata.get("duration") or 1),
            "-i",
            str(fg_path),
            "-filter_complex",
            f"[1:v]{video_scale}[v0];[0:v][v0]overlay=x=36:y=388:shortest=1[base];[base][2:v]overlay=0:0:shortest=1[outv]",
            "-map",
            "[outv]",
            "-map",
            "1:a:0?",
        ]
    else:
        badge_path = output_dir / f"short-{short.pk}-badge.png"
        if logo_path and logo_path.exists():
            logo_path = make_short_logo_badge(logo_path, badge_path, size=170) or logo_path
        args = [ffmpeg_binary(), "-y", "-i", str(input_path)]
        if logo_path and logo_path.exists():
            args += ["-i", str(logo_path)]
        args += [
            "-filter_complex",
            shorts_frame_filter(short, metadata, with_logo=bool(logo_path and logo_path.exists())),
            "-map",
            "[outv]",
            "-map",
            "0:a:0?",
        ]
    args += [
        "-c:v",
        "libx264",
        "-preset",
        getattr(settings, "LIVE_TV_HLS_PRESET", "veryfast"),
        "-pix_fmt",
        "yuv420p",
        "-r",
        "30",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        str(tmp_output),
    ]
    try:
        update_render_progress = progress_updater(ShortsVideo, short.pk)
        run_ffmpeg_command(
            args,
            duration=metadata.get("duration") or 0,
            progress_callback=lambda percent: update_render_progress(1 + (float(percent) * 0.79)),
            timeout=getattr(settings, "LIVE_TV_SHORTS_RENDER_TIMEOUT", 1800),
        )
        tmp_output.replace(final_output)
        rel_path = final_output.relative_to(Path(settings.MEDIA_ROOT)).as_posix()
        short.rendered_video.name = rel_path
        short.video_file.name = rel_path
        short.duration = metadata.get("duration")
        short.hls_status = ShortsVideo.HLSStatus.PENDING
        short.hls_progress_percent = 82
        short.save(update_fields=["rendered_video", "video_file", "duration", "hls_status", "hls_progress_percent", "updated_at"])
        try:
            generate_short_thumbnail(short, final_output)
        except Exception:
            logger.exception("Shorts thumbnail generation failed for %s; continuing with rendered video.", short.pk)
        return final_output
    except Exception as exc:
        tmp_output.unlink(missing_ok=True)
        ShortsVideo.objects.filter(pk=short.pk).update(hls_status=ShortsVideo.HLSStatus.FAILED, hls_progress_percent=0, processing_error=str(exc)[-3000:], updated_at=timezone.now())
        raise


def convert_short_to_hls(short_id):
    short = ShortsVideo.objects.get(pk=short_id)
    if restore_existing_hls_completion(short):
        logger.info("Restored completed Shorts HLS state for %s from existing media.", short.pk)
        return short.hls_master_url
    if not short.video_file:
        raise HLSProcessingError("Short has no video file.")

    input_path = Path(short.video_file.path)
    if not input_path.exists():
        raise HLSProcessingError("Source video file not found.")

    stale_cutoff = timezone.now() - timedelta(minutes=getattr(settings, "LIVE_TV_HLS_PROCESSING_STALE_MINUTES", 20))
    if short.hls_status == ShortsVideo.HLSStatus.COMPLETED and hls_media_file_exists(short.hls_master_url):
        logger.info("Shorts HLS already completed for %s; skipping duplicate conversion.", short.pk)
        return short.hls_master_url
    if short.hls_status == ShortsVideo.HLSStatus.PROCESSING and short.updated_at >= stale_cutoff:
        logger.info("Shorts HLS already processing for %s; skipping duplicate conversion.", short.pk)
        return short.hls_master_url

    other_active = (
        ShortsVideo.objects.filter(hls_status=ShortsVideo.HLSStatus.PROCESSING, updated_at__gte=stale_cutoff)
        .exclude(pk=short.pk)
        .exists()
    )
    if other_active:
        logger.info("Another shorts HLS job is active; leaving short %s pending.", short.pk)
        return short.hls_master_url

    short.hls_status = ShortsVideo.HLSStatus.PROCESSING
    short.hls_progress_percent = max(82, short.hls_progress_percent or 0)
    short.processing_error = ""
    short.save(update_fields=["hls_status", "hls_progress_percent", "processing_error", "updated_at"])

    final_dir = Path(settings.MEDIA_ROOT) / "videos" / str(short.pk) / "hls"
    tmp_parent = final_dir.parent
    tmp_parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = Path(tempfile.mkdtemp(prefix=f"hls-{short.pk}-", dir=str(tmp_parent)))

    try:
        metadata = probe_video(input_path)
        duration = metadata.get("duration") or 0
        update_progress = progress_updater(ShortsVideo, short.pk)
        total_variants = max(1, len(HLS_VARIANTS))
        for variant_index, variant in enumerate(HLS_VARIANTS):
            variant_dir = tmp_dir / variant["name"]
            variant_dir.mkdir(parents=True, exist_ok=True)
            args = [
                ffmpeg_binary(),
                "-y",
                "-i",
                str(input_path),
                "-map",
                "0:v:0",
            ]
            if metadata["has_audio"]:
                args += ["-map", "0:a:0?"]
            args += [
                "-vf",
                scale_filter(metadata, variant["short"]),
                "-c:v",
                "libx264",
                "-preset",
                getattr(settings, "LIVE_TV_HLS_PRESET", "veryfast"),
                "-profile:v",
                "main",
                "-pix_fmt",
                "yuv420p",
                "-r",
                "30",
                "-g",
                "60",
                "-keyint_min",
                "60",
                "-sc_threshold",
                "0",
                "-b:v",
                variant["video_bitrate"],
                "-maxrate",
                variant["video_bitrate"],
                "-bufsize",
                str(int(variant["video_bitrate"].rstrip("k")) * 2) + "k",
            ]
            if metadata["has_audio"]:
                args += ["-c:a", "aac", "-b:a", variant["audio_bitrate"], "-ac", "2"]
            else:
                args += ["-an"]
            args += [
                "-hls_time",
                "2",
                "-hls_playlist_type",
                "vod",
                "-hls_flags",
                "independent_segments",
                "-hls_segment_filename",
                str(variant_dir / "segment_%05d.ts"),
                str(variant_dir / "index.m3u8"),
            ]
            def variant_progress(percent, index=variant_index):
                update_progress(82 + (((index + (percent / 100)) / total_variants) * 17))

            run_ffmpeg_command(args, duration=duration, progress_callback=variant_progress, timeout=getattr(settings, "LIVE_TV_HLS_TIMEOUT", 1800))
            update_progress(82 + (((variant_index + 1) / total_variants) * 17))

        write_master_playlist(tmp_dir, metadata)
        make_public_media_tree(tmp_dir)
        if final_dir.exists():
            shutil.rmtree(final_dir)
        tmp_dir.replace(final_dir)
        short.hls_master_url = f"videos/{short.pk}/hls/master.m3u8"
        short.hls_status = ShortsVideo.HLSStatus.COMPLETED
        short.hls_progress_percent = 100
        short.processing_error = ""
        short.duration = metadata.get("duration")
        short.save(update_fields=["hls_master_url", "hls_status", "hls_progress_percent", "processing_error", "duration", "updated_at"])
        return short.hls_master_url
    except Exception as exc:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)
        ShortsVideo.objects.filter(pk=short.pk).update(
            hls_status=ShortsVideo.HLSStatus.FAILED,
            hls_progress_percent=0,
            processing_error=str(exc)[-3000:],
            updated_at=timezone.now(),
        )
        raise


def convert_live_channel_to_hls(channel_id):
    channel = LiveTVChannel.objects.get(pk=channel_id)
    if restore_existing_hls_completion(channel):
        logger.info("Restored completed Live TV HLS state for %s from existing media.", channel.pk)
        return channel.hls_master_url
    if not channel.video_file:
        raise HLSProcessingError("Live TV channel has no video file.")

    input_path = Path(channel.video_file.path)
    if not input_path.exists():
        raise HLSProcessingError("Source video file not found.")

    stale_cutoff = timezone.now() - timedelta(minutes=getattr(settings, "LIVE_TV_HLS_PROCESSING_STALE_MINUTES", 20))
    if channel.hls_status == LiveTVChannel.HLSStatus.COMPLETED and hls_media_file_exists(channel.hls_master_url):
        if channel.hls_progress_percent != 100:
            LiveTVChannel.objects.filter(pk=channel.pk).update(hls_progress_percent=100, processing_error="", updated_at=timezone.now())
        logger.info("Live TV HLS already completed for %s; skipping duplicate conversion.", channel.pk)
        return channel.hls_master_url
    if channel.hls_status == LiveTVChannel.HLSStatus.PROCESSING and channel.updated_at >= stale_cutoff:
        logger.info("Live TV HLS already processing for %s; skipping duplicate conversion.", channel.pk)
        return channel.hls_master_url

    other_active = (
        LiveTVChannel.objects.filter(hls_status=LiveTVChannel.HLSStatus.PROCESSING, updated_at__gte=stale_cutoff)
        .exclude(pk=channel.pk)
        .exists()
    )
    if other_active:
        logger.info("Another Live TV HLS job is active; leaving channel %s pending.", channel.pk)
        return channel.hls_master_url

    lock_fd, lock_path = acquire_hls_processing_lock("live-channel")
    if lock_fd is None:
        logger.info("Live TV HLS lock is active; leaving channel %s pending.", channel.pk)
        return channel.hls_master_url

    channel.hls_status = LiveTVChannel.HLSStatus.PROCESSING
    channel.hls_progress_percent = 1
    channel.processing_error = ""
    channel.save(update_fields=["hls_status", "hls_progress_percent", "processing_error", "updated_at"])

    tmp_dir = None
    try:
        final_dir = Path(settings.MEDIA_ROOT) / "live-tv" / "hls" / str(channel.pk)
        tmp_parent = final_dir.parent
        tmp_parent.mkdir(parents=True, exist_ok=True)
        tmp_dir = Path(tempfile.mkdtemp(prefix=f"live-hls-{channel.pk}-", dir=str(tmp_parent)))
        metadata = probe_video(input_path)
        duration = metadata.get("duration") or 0
        update_progress = progress_updater(LiveTVChannel, channel.pk)
        total_variants = max(1, len(HLS_VARIANTS))
        for variant_index, variant in enumerate(HLS_VARIANTS):
            variant_dir = tmp_dir / variant["name"]
            variant_dir.mkdir(parents=True, exist_ok=True)
            args = [
                ffmpeg_binary(),
                "-y",
                "-i",
                str(input_path),
                "-map",
                "0:v:0",
            ]
            if metadata["has_audio"]:
                args += ["-map", "0:a:0?"]
            args += [
                "-vf",
                scale_filter(metadata, variant["short"]),
                "-c:v",
                "libx264",
                "-preset",
                getattr(settings, "LIVE_TV_HLS_PRESET", "veryfast"),
                "-profile:v",
                "main",
                "-pix_fmt",
                "yuv420p",
                "-r",
                "30",
                "-g",
                "60",
                "-keyint_min",
                "60",
                "-sc_threshold",
                "0",
                "-b:v",
                variant["video_bitrate"],
                "-maxrate",
                variant["video_bitrate"],
                "-bufsize",
                str(int(variant["video_bitrate"].rstrip("k")) * 2) + "k",
            ]
            if metadata["has_audio"]:
                args += ["-c:a", "aac", "-b:a", variant["audio_bitrate"], "-ac", "2"]
            else:
                args += ["-an"]
            args += [
                "-hls_time",
                "2",
                "-hls_playlist_type",
                "vod",
                "-hls_flags",
                "independent_segments",
                "-hls_segment_filename",
                str(variant_dir / "segment_%05d.ts"),
                str(variant_dir / "index.m3u8"),
            ]
            def variant_progress(percent, index=variant_index):
                update_progress(1 + (((index + (percent / 100)) / total_variants) * 98))

            run_ffmpeg_command(args, duration=duration, progress_callback=variant_progress, timeout=getattr(settings, "LIVE_TV_HLS_TIMEOUT", 1800))
            update_progress(1 + (((variant_index + 1) / total_variants) * 98))

        write_master_playlist(tmp_dir, metadata)
        make_public_media_tree(tmp_dir)
        if final_dir.exists():
            shutil.rmtree(final_dir)
        tmp_dir.replace(final_dir)
        channel.hls_master_url = f"live-tv/hls/{channel.pk}/master.m3u8"
        channel.hls_status = LiveTVChannel.HLSStatus.COMPLETED
        channel.hls_progress_percent = 100
        channel.processing_error = ""
        channel.duration = metadata.get("duration")
        channel.duration_seconds = max(0, int(round(metadata.get("duration") or 0)))
        channel.save(
            update_fields=[
                "hls_master_url",
                "hls_status",
                "hls_progress_percent",
                "processing_error",
                "duration",
                "duration_seconds",
                "updated_at",
            ]
        )
        channel.refresh_from_db(fields=["pending_delete", "auto_add_to_live", "auto_playlist_enabled", "is_active"])
        if (
            not channel.pending_delete
            and channel.is_active
            and channel.auto_add_to_live
            and not channel.auto_playlist_enabled
            and channel.duration_seconds > 0
        ):
            try:
                from .services import add_uploaded_video_to_live_playlist

                add_uploaded_video_to_live_playlist(channel)
            except Exception:
                logger.exception("Live playlist auto-add failed for channel %s", channel.pk)
        try:
            from .notifications import notify_new_video_ready

            notify_new_video_ready(channel.pk)
        except Exception:
            logger.exception("New video push notification failed for channel %s", channel.pk)
        return channel.hls_master_url
    except Exception as exc:
        if tmp_dir and tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)
        LiveTVChannel.objects.filter(pk=channel.pk).update(
            hls_status=LiveTVChannel.HLSStatus.FAILED,
            hls_progress_percent=0,
            processing_error=str(exc)[-3000:],
            updated_at=timezone.now(),
        )
        raise
    finally:
        release_hls_processing_lock(lock_fd, lock_path)

