import json
import logging
import shutil
import time
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import close_old_connections
from django.utils import timezone

from social_downloader.models import SocialMediaDownload

from .formats import video_selector
from .metadata import extract_metadata, import_ytdlp
from .paths import job_output_dir, safe_filename
from .validators import validate_public_media_url

logger = logging.getLogger(__name__)


def ffmpeg_available():
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def total_size_from_info(info):
    total = 0
    for item in info.get("requested_downloads") or []:
        total += item.get("filesize") or 0
    return total or None


def find_output_file(output_dir, before_files):
    candidates = [path for path in output_dir.iterdir() if path.is_file() and path not in before_files and path.name != "metadata.json"]
    if not candidates:
        candidates = [path for path in output_dir.iterdir() if path.is_file() and path.name != "metadata.json"]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def build_download_options(job, output_dir):
    outtmpl = str(output_dir / "%(id)s.%(ext)s")
    common = {
        "outtmpl": outtmpl,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "continuedl": True,
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 30,
        "restrictfilenames": True,
    }
    if job.download_type == SocialMediaDownload.DownloadType.AUDIO:
        if job.audio_format != "best" and not ffmpeg_available():
            raise RuntimeError("FFmpeg is not installed. Audio conversion is not available.")
        common["format"] = "bestaudio/best"
        if job.audio_format and job.audio_format != "best":
            common["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": job.audio_format,
                    "preferredquality": "192",
                }
            ]
        return common

    if not ffmpeg_available():
        raise RuntimeError("FFmpeg is not installed. Video/audio merge is not available.")
    common["format"] = video_selector(job.selected_quality)
    common["merge_output_format"] = "mp4"
    return common


def run_download_job(job_id):
    close_old_connections()
    job = SocialMediaDownload.objects.get(pk=job_id)
    output_dir = None
    try:
        validate_public_media_url(job.source_url)
        metadata = extract_metadata(job.source_url)
        max_size = int(getattr(settings, "SOCIAL_DOWNLOADER_MAX_FILE_SIZE", 500 * 1024 * 1024))
        output_dir, relative_dir = job_output_dir(job)
        metadata_path = output_dir / "metadata.json"
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

        job.status = SocialMediaDownload.Status.PROCESSING
        job.started_at = timezone.now()
        job.title = metadata["title"][:500]
        job.thumbnail_url = metadata["thumbnail_url"][:2000]
        job.duration_seconds = metadata["duration_seconds"]
        job.source_domain = metadata["source_domain"][:255]
        job.extractor_name = metadata["extractor_name"][:100]
        job.progress_percent = 1
        job.error_message = ""
        job.save(
            update_fields=[
                "status",
                "started_at",
                "title",
                "thumbnail_url",
                "duration_seconds",
                "source_domain",
                "extractor_name",
                "progress_percent",
                "error_message",
                "updated_at",
            ]
        )

        last_update = {"time": 0.0, "percent": 0}

        def hook(data):
            status = data.get("status")
            if status == "downloading":
                downloaded = data.get("downloaded_bytes") or 0
                total = data.get("total_bytes") or data.get("total_bytes_estimate")
                percent = int(downloaded * 100 / total) if total else 5
                now = time.monotonic()
                if now - last_update["time"] >= 2 or percent - last_update["percent"] >= 2:
                    last_update.update({"time": now, "percent": percent})
                    SocialMediaDownload.objects.filter(pk=job.pk).update(
                        progress_percent=max(1, min(95, percent)),
                        downloaded_bytes=downloaded,
                        total_bytes=total,
                    )
            elif status == "finished":
                SocialMediaDownload.objects.filter(pk=job.pk).update(progress_percent=96)

        YoutubeDL, _DownloadError = import_ytdlp()
        ydl_opts = build_download_options(job, output_dir)
        ydl_opts["progress_hooks"] = [hook]
        before_files = set(output_dir.iterdir())
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(job.source_url, download=True)

        output_file = find_output_file(output_dir, before_files)
        if not output_file:
            raise RuntimeError("Download finished but output file was not found.")

        file_size = output_file.stat().st_size
        if file_size > max_size:
            output_file.unlink(missing_ok=True)
            raise RuntimeError(f"File too large. Maximum allowed size is {max_size // (1024 * 1024)} MB.")

        extension = output_file.suffix.lstrip(".") or ("mp3" if job.download_type == "audio" else "mp4")
        final_name = safe_filename(job.title, extension)
        final_path = output_dir / final_name
        if output_file != final_path:
            output_file.rename(final_path)
        relative_file = Path(relative_dir) / final_name

        job.status = SocialMediaDownload.Status.COMPLETED
        job.progress_percent = 100
        job.downloaded_bytes = file_size
        job.total_bytes = total_size_from_info(info) or file_size
        job.relative_file_path = relative_file.as_posix()
        job.original_filename = Path(info.get("_filename") or "").name[:500]
        job.stored_filename = final_name[:500]
        job.file_extension = extension[:20]
        job.file_size = file_size
        job.completed_at = timezone.now()
        job.error_message = ""
        job.save()
        logger.info("social_downloader job completed", extra={"job_id": job.pk, "user_id": job.user_id, "extractor": job.extractor_name})
    except (ValidationError, Exception) as exc:
        message = "; ".join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
        SocialMediaDownload.objects.filter(pk=job_id).update(
            status=SocialMediaDownload.Status.FAILED,
            error_message=message[:2000],
            progress_percent=0,
            updated_at=timezone.now(),
        )
        if output_dir:
            for path in output_dir.glob("*.part"):
                path.unlink(missing_ok=True)
        logger.warning("social_downloader job failed", extra={"job_id": job_id, "error": message[:200]})
    finally:
        close_old_connections()

