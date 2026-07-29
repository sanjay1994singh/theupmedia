import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .hls import convert_live_channel_to_hls, convert_short_to_hls, render_short_frame
from .account_emails import send_account_email
from .models import AccountDeletionRequest, LiveTVChannel, MobileAdminToken, ShortsVideo
from .views import run_media_download_job, run_social_render_job
from .services import cleanup_expired_live_video_sources, live_playlist_cutoff, repair_live_tv_health


logger = logging.getLogger(__name__)


@shared_task(name="live_tv.render_social_video")
def render_social_video_task(job_id):
    run_social_render_job(job_id)
    cleanup_expired_live_video_sources()


@shared_task(bind=True, name="live_tv.render_live_broadcast_video", autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 2})
def render_live_broadcast_video_task(self, job_id):
    run_social_render_job(job_id, raise_errors=True)
    cleanup_expired_live_video_sources()


@shared_task(name="live_tv.download_media")
def download_media_task(job_id):
    run_media_download_job(job_id)


@shared_task(name="live_tv.process_short_hls")
def process_short_hls_task(short_id):
    short = ShortsVideo.objects.filter(pk=short_id).first()
    if not short:
        return
    if short.hls_status == ShortsVideo.HLSStatus.COMPLETED and short.hls_master_url:
        return
    if not short.rendered_video:
        render_short_frame(short_id)
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
    initial_status = (
        LiveTVChannel.objects.filter(pk=channel_id)
        .values_list("hls_status", flat=True)
        .first()
    )
    if initial_status in {None, LiveTVChannel.HLSStatus.COMPLETED}:
        # A task can be restored by Redis after a worker restart. Completed or
        # deleted uploads must not start/extend the serial queue again.
        return

    try:
        convert_live_channel_to_hls(channel_id)
    except Exception:
        # A bad upload must not block every video behind it in the serial HLS queue.
        logger.exception("Live TV HLS processing failed for channel %s.", channel_id)
    cleanup_expired_live_video_sources()
    try:
        repair_live_tv_health(queue_hls=False, queue_renders=True)
    except Exception:
        logger.exception("Live TV health repair failed after channel %s.", channel_id)

    current_status = (
        LiveTVChannel.objects.filter(pk=channel_id)
        .values_list("hls_status", flat=True)
        .first()
    )
    if current_status == LiveTVChannel.HLSStatus.PENDING:
        # The converter intentionally leaves a job pending when another HLS
        # process/lock is active. Do not bounce between pending channels and
        # create an unbounded Celery task chain.
        return

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
    result = repair_live_tv_health(queue_hls=True, queue_renders=True)
    process_due_account_deletions_task()
    return result


@shared_task(name="live_tv.process_due_account_deletions")
def process_due_account_deletions_task():
    from django.contrib.auth import get_user_model
    from django.db import transaction

    due_ids = list(
        AccountDeletionRequest.objects.filter(
            status=AccountDeletionRequest.Status.PENDING,
            scheduled_for__lte=timezone.now(),
        ).values_list("pk", flat=True)[:100]
    )
    User = get_user_model()
    completed = 0
    for request_id in due_ids:
        try:
            with transaction.atomic():
                deletion = AccountDeletionRequest.objects.select_for_update().get(pk=request_id)
                if deletion.status != AccountDeletionRequest.Status.PENDING or deletion.scheduled_for > timezone.now():
                    continue
                user = User.objects.filter(pk=deletion.user_id_snapshot).first()
                if user:
                    for field_name in ("avatar", "cover_image"):
                        file_field = getattr(user, field_name, None)
                        if file_field:
                            file_field.delete(save=False)
                    MobileAdminToken.objects.filter(user=user).delete()
                    user.delete()
                deletion.status = AccountDeletionRequest.Status.COMPLETED
                deletion.completed_at = timezone.now()
                deletion.last_error = ""
                deletion.save(update_fields=["status", "completed_at", "last_error"])
            send_account_email("deleted", deletion.email_snapshot, display_name=deletion.full_name_snapshot or deletion.username_snapshot)
            completed += 1
        except Exception as exc:
            logger.exception("Scheduled account deletion %s failed", request_id)
            AccountDeletionRequest.objects.filter(pk=request_id).update(last_error=str(exc)[:2000])
    return {"completed": completed, "checked": len(due_ids)}


@shared_task(name="live_tv.cleanup_expired_live_sources")
def cleanup_expired_live_sources_task():
    return cleanup_expired_live_video_sources()
