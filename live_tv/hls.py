import json
import logging
import shutil
import subprocess
import tempfile
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from .models import ShortsVideo
from .models import LiveTVChannel


logger = logging.getLogger(__name__)


ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
ALLOWED_VIDEO_MIME_PREFIXES = ("video/",)
HLS_VARIANTS = (
    {"name": "360p", "short": 360, "video_bitrate": "650k", "audio_bitrate": "64k", "bandwidth": 800000},
    {"name": "480p", "short": 480, "video_bitrate": "1100k", "audio_bitrate": "96k", "bandwidth": 1300000},
    {"name": "720p", "short": 720, "video_bitrate": "2200k", "audio_bitrate": "128k", "bandwidth": 2600000},
)


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
        if item.is_dir():
            item.chmod(0o755)
        else:
            item.chmod(0o644)
    path.chmod(0o755)


def hls_media_file_exists(media_path):
    return bool(media_path and (Path(settings.MEDIA_ROOT) / media_path).exists())


def convert_short_to_hls(short_id):
    short = ShortsVideo.objects.get(pk=short_id)
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
    short.processing_error = ""
    short.save(update_fields=["hls_status", "processing_error", "updated_at"])

    final_dir = Path(settings.MEDIA_ROOT) / "videos" / str(short.pk) / "hls"
    tmp_parent = final_dir.parent
    tmp_parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = Path(tempfile.mkdtemp(prefix=f"hls-{short.pk}-", dir=str(tmp_parent)))

    try:
        metadata = probe_video(input_path)
        for variant in HLS_VARIANTS:
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
            run_command(args, timeout=getattr(settings, "LIVE_TV_HLS_TIMEOUT", 1800))

        write_master_playlist(tmp_dir, metadata)
        make_public_media_tree(tmp_dir)
        if final_dir.exists():
            shutil.rmtree(final_dir)
        tmp_dir.replace(final_dir)
        short.hls_master_url = f"videos/{short.pk}/hls/master.m3u8"
        short.hls_status = ShortsVideo.HLSStatus.COMPLETED
        short.processing_error = ""
        short.duration = metadata.get("duration")
        short.save(update_fields=["hls_master_url", "hls_status", "processing_error", "duration", "updated_at"])
        return short.hls_master_url
    except Exception as exc:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)
        ShortsVideo.objects.filter(pk=short.pk).update(
            hls_status=ShortsVideo.HLSStatus.FAILED,
            processing_error=str(exc)[-3000:],
            updated_at=timezone.now(),
        )
        raise


def convert_live_channel_to_hls(channel_id):
    channel = LiveTVChannel.objects.get(pk=channel_id)
    if not channel.video_file:
        raise HLSProcessingError("Live TV channel has no video file.")

    input_path = Path(channel.video_file.path)
    if not input_path.exists():
        raise HLSProcessingError("Source video file not found.")

    channel.hls_status = LiveTVChannel.HLSStatus.PROCESSING
    channel.processing_error = ""
    channel.save(update_fields=["hls_status", "processing_error", "updated_at"])

    final_dir = Path(settings.MEDIA_ROOT) / "live-tv" / "hls" / str(channel.pk)
    tmp_parent = final_dir.parent
    tmp_parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = Path(tempfile.mkdtemp(prefix=f"live-hls-{channel.pk}-", dir=str(tmp_parent)))

    try:
        metadata = probe_video(input_path)
        for variant in HLS_VARIANTS:
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
            run_command(args, timeout=getattr(settings, "LIVE_TV_HLS_TIMEOUT", 1800))

        write_master_playlist(tmp_dir, metadata)
        make_public_media_tree(tmp_dir)
        if final_dir.exists():
            shutil.rmtree(final_dir)
        tmp_dir.replace(final_dir)
        channel.hls_master_url = f"live-tv/hls/{channel.pk}/master.m3u8"
        channel.hls_status = LiveTVChannel.HLSStatus.COMPLETED
        channel.processing_error = ""
        channel.duration = metadata.get("duration")
        channel.duration_seconds = max(0, int(round(metadata.get("duration") or 0)))
        channel.save(
            update_fields=[
                "hls_master_url",
                "hls_status",
                "processing_error",
                "duration",
                "duration_seconds",
                "updated_at",
            ]
        )
        if channel.auto_add_to_live and not channel.auto_playlist_enabled and channel.duration_seconds > 0:
            try:
                from .services import add_uploaded_video_to_live_playlist

                add_uploaded_video_to_live_playlist(channel)
            except Exception:
                logger.exception("Live playlist auto-add failed for channel %s", channel.pk)
        return channel.hls_master_url
    except Exception as exc:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)
        LiveTVChannel.objects.filter(pk=channel.pk).update(
            hls_status=LiveTVChannel.HLSStatus.FAILED,
            processing_error=str(exc)[-3000:],
            updated_at=timezone.now(),
        )
        raise
