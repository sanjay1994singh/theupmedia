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
        if item.is_dir():
            item.chmod(0o755)
        else:
            item.chmod(0o644)
    path.chmod(0o755)


def hls_media_file_exists(media_path):
    return bool(media_path and (Path(settings.MEDIA_ROOT) / media_path).exists())


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
    short.hls_progress_percent = 1
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
                update_progress(1 + (((index + (percent / 100)) / total_variants) * 98))

            run_ffmpeg_command(args, duration=duration, progress_callback=variant_progress, timeout=getattr(settings, "LIVE_TV_HLS_TIMEOUT", 1800))
            update_progress(1 + (((variant_index + 1) / total_variants) * 98))

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

    final_dir = Path(settings.MEDIA_ROOT) / "live-tv" / "hls" / str(channel.pk)
    tmp_parent = final_dir.parent
    tmp_parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = Path(tempfile.mkdtemp(prefix=f"live-hls-{channel.pk}-", dir=str(tmp_parent)))

    try:
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
            hls_progress_percent=0,
            processing_error=str(exc)[-3000:],
            updated_at=timezone.now(),
        )
        raise
    finally:
        release_hls_processing_lock(lock_fd, lock_path)

