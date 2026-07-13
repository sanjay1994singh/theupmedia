from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from .forms import DownloadStartForm, MetadataFetchForm
from .models import SocialMediaDownload
from .services.formats import AUDIO_FORMAT_CHOICES, VIDEO_QUALITY_CHOICES
from .services.metadata import extract_metadata
from .services.paths import resolve_download_path
from .services.validators import enforce_job_limits


def user_downloads(user):
    queryset = SocialMediaDownload.objects.select_related("user")
    if user.is_superuser:
        return queryset
    return queryset.filter(user=user)


def enqueue_download(job_id):
    try:
        from .tasks import run_social_download_task

        run_social_download_task.delay(job_id)
        return "celery"
    except Exception as exc:
        SocialMediaDownload.objects.filter(pk=job_id).update(error_message=f"Celery enqueue failed: {exc}")
        return "manual-worker"


@login_required
def downloader_home(request):
    metadata = None
    fetch_form = MetadataFetchForm()
    start_form = DownloadStartForm(initial={"download_type": "video", "video_quality": "best", "audio_format": "mp3"})

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "fetch":
            fetch_form = MetadataFetchForm(request.POST)
            if fetch_form.is_valid():
                try:
                    metadata = extract_metadata(fetch_form.cleaned_data["url"])
                    start_form = DownloadStartForm(initial={"url": metadata["source_url"], "download_type": "video", "video_quality": "best", "audio_format": "mp3"})
                except ValidationError as exc:
                    fetch_form.add_error("url", exc)
                except RuntimeError as exc:
                    fetch_form.add_error("url", str(exc))
        elif action == "download":
            start_form = DownloadStartForm(request.POST)
            if start_form.is_valid():
                try:
                    enforce_job_limits(request.user)
                    metadata = extract_metadata(start_form.cleaned_data["url"])
                    job = SocialMediaDownload.objects.create(
                        user=request.user,
                        source_url=metadata["source_url"],
                        source_domain=metadata["source_domain"][:255],
                        extractor_name=metadata["extractor_name"][:100],
                        title=metadata["title"][:500],
                        thumbnail_url=metadata["thumbnail_url"][:2000],
                        duration_seconds=metadata["duration_seconds"],
                        download_type=start_form.cleaned_data["download_type"],
                        selected_quality=start_form.cleaned_data.get("video_quality") or "",
                        audio_format=start_form.cleaned_data.get("audio_format") or "",
                    )
                    backend = enqueue_download(job.pk)
                    messages.success(request, f"Download job start ho gaya ({backend}). History me progress dekhein.")
                    return redirect("social_downloader:history")
                except ValidationError as exc:
                    start_form.add_error(None, exc)
                except RuntimeError as exc:
                    start_form.add_error(None, str(exc))

    recent_jobs = user_downloads(request.user)[:8]
    return render(
        request,
        "social_downloader/home.html",
        {
            "fetch_form": fetch_form,
            "start_form": start_form,
            "metadata": metadata,
            "recent_jobs": recent_jobs,
            "video_quality_choices": VIDEO_QUALITY_CHOICES,
            "audio_format_choices": AUDIO_FORMAT_CHOICES,
        },
    )


@login_required
def download_history(request):
    jobs = user_downloads(request.user)
    status = request.GET.get("status", "").strip()
    download_type = request.GET.get("type", "").strip()
    if status:
        jobs = jobs.filter(status=status)
    if download_type:
        jobs = jobs.filter(download_type=download_type)
    paginator = Paginator(jobs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "social_downloader/history.html", {"page_obj": page_obj, "status": status, "download_type": download_type})


@login_required
@require_GET
def download_status(request, pk):
    job = get_object_or_404(user_downloads(request.user), pk=pk)
    return JsonResponse(
        {
            "id": job.pk,
            "status": job.status,
            "progress_percent": job.progress_percent,
            "file_size": job.file_size,
            "error_message": job.error_message,
            "file_url": job.get_file_url(),
        }
    )


@login_required
def download_file(request, pk):
    job = get_object_or_404(user_downloads(request.user), pk=pk)
    if job.status != SocialMediaDownload.Status.COMPLETED or not job.relative_file_path:
        raise PermissionDenied("File is not ready.")
    file_path = resolve_download_path(job.relative_file_path)
    if not file_path.exists() or not file_path.is_file():
        raise PermissionDenied("File is missing.")
    return FileResponse(file_path.open("rb"), as_attachment=True, filename=job.stored_filename or Path(file_path).name)


@login_required
@require_POST
def delete_download(request, pk):
    job = get_object_or_404(user_downloads(request.user), pk=pk)
    if job.relative_file_path:
        try:
            resolve_download_path(job.relative_file_path).unlink(missing_ok=True)
        except ValueError:
            pass
    job.delete()
    messages.success(request, "Download history delete ho gayi.")
    return redirect("social_downloader:history")
