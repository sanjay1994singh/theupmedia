import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .hls import convert_live_channel_to_hls, convert_short_to_hls
from .models import LiveTVChannel, ShortsVideo
from .views import run_media_download_job, run_social_render_job
from .services import live_playlist_cutoff, repair_live_tv_health


logger = logging.getLogger(__name__)


@shared_task(name="live_tv.render_social_video")
def render_social_video_task(job_id):
    run_social_render_job(job_id)


@shared_task(bind=True, name="live_tv.render_live_broadcast_video", autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 2})
def render_live_broadcast_video_task(self, job_id):
    run_social_render_job(job_id, raise_errors=True)


@shared_task(name="live_tv.download_media")
def download_media_task(job_id):
    run_media_download_job(job_id)


@shared_task(name="live_tv.process_short_hls")
def process_short_hls_task(short_id):
    convert_short_to_hls(short_id)
    next_short = (
        ShortsVideo.objects.filter(is_published=True, hls_status=ShortsVideo.HLSStatus.PENDING)
        .exclude(pk=short_id)
        .order_by("display_order", "pk")
        .first()
    )
    if next_short:
        process_short_hls_task.delay(next_short.pk)


@shared_task(name="live_tv.process_live_channel_hls")
def process_live_channel_hls_task(channel_id):
    try:
        convert_live_channel_to_hls(channel_id)
    except Exception:
        # A bad upload must not block every video behind it in the serial HLS queue.
        logger.exception("Live TV HLS processing failed for channel %s.", channel_id)
    try:
        repair_live_tv_health(queue_hls=False, queue_renders=True)
    except Exception:
        logger.exception("Live TV health repair failed after channel %s.", channel_id)

    stale_cutoff = timezone.now() - timedelta(minutes=getattr(settings, "LIVE_TV_HLS_PROCESSING_STALE_MINUTES", 20))
    if LiveTVChannel.objects.filter(hls_status=LiveTVChannel.HLSStatus.PROCESSING, updated_at__gte=stale_cutoff).exists():
        return
    next_channel = (
        LiveTVChannel.objects.filter(
            source_type=LiveTVChannel.SourceType.DIRECT,
            video_file__isnull=False,
            hls_status=LiveTVChannel.HLSStatus.PENDING,
            created_at__gte=live_playlist_cutoff(timezone.now()),
            auto_add_to_live=True,
            is_active=True,
        )
        .exclude(pk=channel_id)
        .order_by("display_order", "pk")
        .first()
    )
    if next_channel:
        process_live_channel_hls_task.delay(next_channel.pk)


@shared_task(name="live_tv.cleanup_rendered_video_temps")
def cleanup_rendered_video_temps_task(hours=24):
    from django.core.management import call_command

    call_command("cleanup_rendered_video_temps", hours=hours)


@shared_task(name="live_tv.live_tv_health_watchdog")
def live_tv_health_watchdog_task():
    return repair_live_tv_health(queue_hls=True, queue_renders=True)
