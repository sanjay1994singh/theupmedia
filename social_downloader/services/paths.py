import re
import os
import unicodedata
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.utils import timezone


RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "LPT1", "LPT2"}


def safe_filename(value, extension="mp4"):
    stem = Path(value or "theupmedia-download").stem
    stem = stem.replace("\x00", "")
    stem = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode("ascii")
    stem = re.sub(r"[\\/:\*\?\"<>\|]+", "-", stem)
    stem = re.sub(r"[^A-Za-z0-9._() -]+", "-", stem)
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


def open_download_file(relative_path):
    try:
        path = resolve_download_path(relative_path)
        return path.open("rb"), path.name
    except UnicodeEncodeError:
        media_root = Path(settings.MEDIA_ROOT).resolve()
        parts = Path(relative_path).parts
        if any(part in {"", ".", ".."} for part in parts):
            raise ValueError("Invalid file path.")
        root_bytes = os.fsencode(str(media_root))
        target_bytes = root_bytes
        for part in parts:
            target_bytes = os.path.join(target_bytes, part.encode("utf-8"))
        real_root = os.path.realpath(root_bytes)
        real_target = os.path.realpath(target_bytes)
        if not (real_target == real_root or real_target.startswith(real_root + os.sep.encode())):
            raise ValueError("Invalid file path.")
        handle = os.fdopen(os.open(real_target, os.O_RDONLY), "rb")
        return handle, parts[-1]
