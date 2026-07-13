import re
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.utils import timezone


RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "LPT1", "LPT2"}


def safe_filename(value, extension="mp4"):
    stem = Path(value or "theupmedia-download").stem
    stem = stem.replace("\x00", "")
    stem = re.sub(r"[\\/:\*\?\"<>\|]+", "-", stem)
    stem = re.sub(r"\s+", " ", stem).strip(" ._-")
    if not stem or stem.upper() in RESERVED_NAMES:
        stem = "theupmedia-download"
    stem = stem[:90]
    extension = (extension or "mp4").lstrip(".")[:12]
    return f"{stem}-{uuid4().hex[:8]}.{extension}"


def job_relative_dir(job):
    local_time = timezone.localtime()
    return Path("social_downloads") / local_time.strftime("%Y/%m/%d") / f"{local_time.strftime('%H-%M-%S')}_job-{job.pk}"


def job_output_dir(job):
    relative = job_relative_dir(job)
    output_dir = Path(settings.MEDIA_ROOT) / relative
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir, relative


def resolve_download_path(relative_path):
    media_root = Path(settings.MEDIA_ROOT).resolve()
    target = (media_root / relative_path).resolve()
    if media_root not in target.parents and target != media_root:
        raise ValueError("Invalid file path.")
    return target

