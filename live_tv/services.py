import logging
import threading
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

from .models import (
    LiveTVChannel,
    LiveTVPlaylistCycle,
    LiveTVPlaylistCycleItem,
    LiveTVPlaylistItem,
    LiveTVSetting,
    SocialRenderedVideo,
)

logger = logging.getLogger(__name__)


LIVE_PLAYLIST_MAX_AGE_HOURS = 48


def live_playlist_max_age_hours():
    try:
        return max(1, int(getattr(settings, "LIVE_TV_PLAYLIST_MAX_AGE_HOURS", LIVE_PLAYLIST_MAX_AGE_HOURS)))
    except (TypeError, ValueError):
        return LIVE_PLAYLIST_MAX_AGE_HOURS


def live_playlist_cutoff(at=None):
    at = at or timezone.now()
    return at - timedelta(hours=live_playlist_max_age_hours())


def live_playlist_video_is_fresh(video, at=None):
    if not video or not getattr(video, "created_at", None):
        return True
    return video.created_at >= live_playlist_cutoff(at)


def live_video_hls_ready(video):
    """True only when a live playlist video has a usable HLS master playlist."""
    if not video or video.source_type != LiveTVChannel.SourceType.DIRECT:
        return False
    if video.hls_status != LiveTVChannel.HLSStatus.COMPLETED or not video.hls_master_url:
        return False
    try:
        from .hls import hls_media_file_exists

        return hls_media_file_exists(video.hls_master_url)
    except Exception:
        logger.exception("Live TV HLS readiness check failed for video %s", getattr(video, "pk", None))
        return False


def live_playlist_video_is_streamable(video, at=None):
    return bool(live_playlist_video_is_fresh(video, at=at) and live_video_hls_ready(video))


def expire_old_live_playlist_items(channel, at=None):
    if not channel or not channel.pk:
        return 0
    at = at or timezone.now()
    cutoff = live_playlist_cutoff(at)
    with transaction.atomic():
        locked_channel = LiveTVChannel.objects.select_for_update().get(pk=channel.pk)
        old_items = list(
            locked_channel.playlist_items.select_for_update()
            .filter(is_active=True, video__created_at__lt=cutoff)
            .select_related("video")
        )
        if not old_items:
            return 0
        old_item_ids = [item.pk for item in old_items]
        LiveTVPlaylistItem.objects.filter(pk__in=old_item_ids).update(
            is_active=False,
            removed_at=at,
            updated_at=at,
        )
        normalize_playlist_positions(locked_channel)
        locked_channel.playlist_version += 1
        locked_channel.last_playlist_update = at
        if not locked_channel.playlist_items.filter(is_active=True, duration_seconds__gt=0, video__hls_status=LiveTVChannel.HLSStatus.COMPLETED, video__hls_master_url__gt="").exists():
            locked_channel.playback_started_at = None
        locked_channel.playlist_cycles.all().delete()
        locked_channel.save(update_fields=["playlist_version", "last_playlist_update", "playback_started_at", "updated_at"])
        return len(old_item_ids)


def queue_broadcast_render_task(job_id):
    queued_with_celery = False
    if getattr(settings, "LIVE_TV_RENDER_USE_CELERY", True):
        try:
            from .tasks import render_live_broadcast_video_task

            render_live_broadcast_video_task.delay(job_id)
            queued_with_celery = True
        except Exception as exc:
            SocialRenderedVideo.objects.filter(pk=job_id).update(
                error_message=f"Celery enqueue failed, fallback thread started: {exc}",
            )

    if queued_with_celery and getattr(settings, "LIVE_TV_RENDER_THREAD_FALLBACK", True):
        from .views import run_social_render_job_if_stale

        threading.Thread(target=run_social_render_job_if_stale, args=(job_id, 45), daemon=True).start()
        return "celery+fallback"

    from .views import run_social_render_job

    threading.Thread(target=run_social_render_job, args=(job_id,), daemon=True).start()
    return "thread"


def get_main_live_channel(create=False):
    channel = (
        LiveTVChannel.objects.filter(
            source_type=LiveTVChannel.SourceType.PLAYLIST,
            auto_playlist_enabled=True,
            is_active=True,
        )
        .order_by("display_order", "pk")
        .first()
    )
    if channel or not create:
        return channel
    return LiveTVChannel.objects.create(
        title="The Up Media Live",
        source_type=LiveTVChannel.SourceType.PLAYLIST,
        auto_playlist_enabled=True,
        auto_add_to_live=False,
        is_active=True,
        is_live=True,
        loop_enabled=True,
        target_playlist_duration_seconds=10800,
        display_order=0,
    )


def validate_playlist_video(video, check_storage=True):
    errors = []
    if video.source_type != LiveTVChannel.SourceType.DIRECT:
        errors.append("Only direct uploaded videos are eligible.")
    if video.auto_playlist_enabled:
        errors.append("The main playlist channel cannot be used as a video.")
    if not video.auto_add_to_live:
        errors.append("Auto-add is disabled for this video.")
    if not video.is_active:
        errors.append("Video is inactive.")
    if not live_playlist_video_is_fresh(video):
        errors.append(f"Video is older than {live_playlist_max_age_hours()} hours and cannot stream on Live TV.")
    if not video.video_file or not video.video_file.name:
        errors.append("Video file is missing.")
    elif check_storage:
        try:
            if not video.video_file.storage.exists(video.video_file.name):
                errors.append("Video file does not exist in storage.")
        except (OSError, ValueError) as exc:
            errors.append(f"Video storage check failed: {exc}")
    if video.effective_duration_seconds <= 0:
        errors.append("Video duration must be greater than zero.")
    if not live_video_hls_ready(video):
        errors.append("Video HLS is not ready yet; Live TV uses HLS only.")
    if errors:
        raise ValidationError(errors)
    return True


def normalize_playlist_positions(channel):
    items = list(channel.playlist_items.filter(is_active=True).order_by("position", "pk"))
    changed = []
    for position, item in enumerate(items):
        if item.position != position:
            item.position = position
            changed.append(item)
    if changed:
        LiveTVPlaylistItem.objects.bulk_update(changed, ["position", "updated_at"])
    return items


def _create_cycle(channel, items, starts_at, version):
    items = [item for item in items if item.is_active and item.duration_seconds > 0]
    if not items:
        return None
    cycle = LiveTVPlaylistCycle.objects.create(
        channel=channel,
        version=version,
        starts_at=starts_at,
        total_duration_seconds=sum(item.duration_seconds for item in items),
    )
    LiveTVPlaylistCycleItem.objects.bulk_create(
        [
            LiveTVPlaylistCycleItem(
                cycle=cycle,
                playlist_item=item,
                video=item.video,
                position=position,
                duration_seconds=item.duration_seconds,
            )
            for position, item in enumerate(items)
        ]
    )
    return cycle


def playlist_item_start_offset_seconds(cycle_item):
    if not cycle_item or not cycle_item.cycle_id:
        return 0.0
    cycle = getattr(cycle_item, "cycle", None)
    channel = getattr(cycle, "channel", None)
    broadcast_offset = 0.0
    if cycle and channel and cycle.starts_at and channel.playback_started_at:
        broadcast_offset = max(0.0, (cycle.starts_at - channel.playback_started_at).total_seconds())
    previous_items = (
        LiveTVPlaylistCycleItem.objects.filter(cycle_id=cycle_item.cycle_id)
        .filter(position__lt=cycle_item.position)
        .only("duration_seconds")
    )
    item_offset = float(sum(max(0, item.duration_seconds or 0) for item in previous_items))
    return broadcast_offset + item_offset


def broadcast_snapshot_for(video, channel, playlist_item, cycle_item):
    setting = LiveTVSetting.get_solo()
    headlines = list(
        video.rotating_headlines.filter(is_active=True)
        .order_by("position", "pk")
        .values_list("text", flat=True)
    )
    if not headlines and (video.headline or "").strip():
        headlines = [video.headline.strip()]
    headline = headlines[0] if headlines else ""
    lower_label = video.lower_third_label or ""
    title = headline or video.title or f"{channel.title} {timezone.localtime().strftime('%Y-%m-%d %H:%M')}"
    ticker_time_offset = playlist_item_start_offset_seconds(cycle_item)
    return {
        "title": title,
        "headline": headline,
        "headlines": headlines,
        "headline_change_seconds": max(1, min(60, int(video.headline_change_seconds or 2))),
        "repeat_headlines": video.repeat_headlines,
        "headline_label": lower_label,
        "lower_third_label": lower_label,
        "reporter_label": video.reporter_label or "",
        "reporter_name": video.reporter_name or "",
        "ticker_label": setting.default_ticker_label,
        "ticker_text": setting.default_ticker_text,
        "ticker_speed_seconds": setting.ticker_speed_seconds,
        "mobile_ticker_speed_seconds": setting.mobile_ticker_speed_seconds,
        "ticker_time_offset_seconds": ticker_time_offset,
        "ticker_style": "red_white_slant",
        "channel_name": setting.name,
        "channel_logo": setting.channel_logo.name if setting.channel_logo else "",
        "live_label": setting.live_label,
        "show_channel_logo": setting.show_channel_logo,
        "show_live_badge": setting.show_live_badge,
        "show_lower_third": setting.show_lower_third and bool(lower_label or headlines),
        "show_ticker": setting.show_ticker,
        "render_format": "16:9",
        "frame_template": "broadcast_live_tv",
        "frame_category": "live_broadcast",
        "source_video_id": video.pk,
        "live_channel_id": channel.pk,
        "playlist_item_id": playlist_item.pk if playlist_item else None,
        "cycle_id": cycle_item.cycle_id if cycle_item else None,
        "cycle_item_id": cycle_item.pk if cycle_item else None,
        "duration_seconds": video.effective_duration_seconds,
    }


LIVE_BROADCAST_VISUAL_SNAPSHOT_KEYS = (
    "headline",
    "headlines",
    "headline_change_seconds",
    "repeat_headlines",
    "headline_label",
    "lower_third_label",
    "ticker_label",
    "ticker_text",
    "ticker_speed_seconds",
    "mobile_ticker_speed_seconds",
    "ticker_style",
    "channel_name",
    "channel_logo",
    "live_label",
    "show_channel_logo",
    "show_live_badge",
    "show_lower_third",
    "show_ticker",
    "render_format",
    "frame_template",
    "frame_category",
    "duration_seconds",
)


def live_broadcast_visual_snapshot(snapshot):
    return {key: (snapshot or {}).get(key) for key in LIVE_BROADCAST_VISUAL_SNAPSHOT_KEYS}


def live_broadcast_render_identity(channel, video, playlist_item, snapshot):
    # A source upload is rendered only once, regardless of later playlist
    # cycles, ticker changes, channel changes, rebuilds, or retries.
    return f"live:source:v3:{video.pk}"


def same_live_broadcast_render_jobs(channel, video, playlist_item):
    return SocialRenderedVideo.objects.filter(
        source_video=video,
        frame_category="live_broadcast",
        frame_template="broadcast_live_tv",
        render_format="16:9",
        is_active=True,
    )


def matching_live_broadcast_render_job(queryset, snapshot, render_key=None):
    if render_key:
        exact = queryset.filter(render_key=render_key).first()
        if exact:
            return exact
    wanted_snapshot = live_broadcast_visual_snapshot(snapshot)
    for job in queryset.order_by("-completed_at", "-updated_at", "-created_at")[:25]:
        if live_broadcast_visual_snapshot(job.snapshot) == wanted_snapshot:
            return job
    return None


def completed_live_broadcast_render_job(channel, video, playlist_item, snapshot, render_key):
    queryset = (
        same_live_broadcast_render_jobs(channel, video, playlist_item)
        .filter(status__in=[SocialRenderedVideo.Status.COMPLETED, SocialRenderedVideo.Status.DONE])
        .exclude(rendered_video="")
    )
    return queryset.order_by("completed_at", "created_at", "pk").first()


def queueable_live_broadcast_render_job(channel, video, playlist_item, snapshot, render_key):
    queryset = same_live_broadcast_render_jobs(channel, video, playlist_item).filter(
        status__in=[SocialRenderedVideo.Status.PENDING, SocialRenderedVideo.Status.PROCESSING]
    )
    return queryset.order_by("created_at", "pk").first()


def mark_duplicate_live_render_jobs_skipped(canonical_job):
    if not canonical_job or not canonical_job.source_video_id:
        return 0
    queryset = SocialRenderedVideo.objects.filter(
        source_video_id=canonical_job.source_video_id,
        frame_category=canonical_job.frame_category,
        frame_template=canonical_job.frame_template,
        render_format=canonical_job.render_format,
        status__in=[SocialRenderedVideo.Status.PENDING, SocialRenderedVideo.Status.PROCESSING],
    ).exclude(pk=canonical_job.pk)
    return queryset.update(
        status=SocialRenderedVideo.Status.DONE,
        progress_percent=100,
        is_active=False,
        error_message=f"Duplicate skipped. Canonical render id: {canonical_job.pk}",
        completed_at=timezone.now(),
        updated_at=timezone.now(),
    )


def create_broadcast_render_job(cycle_item):
    cycle_item = (
        LiveTVPlaylistCycleItem.objects.select_related(
            "cycle__channel",
            "playlist_item",
            "video",
        )
        .get(pk=cycle_item.pk)
    )
    channel = cycle_item.cycle.channel
    video = cycle_item.video
    playlist_item = cycle_item.playlist_item
    if not video.video_file:
        return None, False
    broadcast_session_id = f"cycle-{cycle_item.cycle_id}-v{cycle_item.cycle.version}-item-{cycle_item.pk}"
    snapshot = broadcast_snapshot_for(video, channel, playlist_item, cycle_item)
    render_key = live_broadcast_render_identity(channel, video, playlist_item, snapshot)

    completed_job = completed_live_broadcast_render_job(channel, video, playlist_item, snapshot, render_key)
    if completed_job:
        mark_duplicate_live_render_jobs_skipped(completed_job)
        completed_job._render_should_enqueue = False
        return completed_job, False

    active_job = queueable_live_broadcast_render_job(channel, video, playlist_item, snapshot, render_key)
    if active_job:
        active_job._render_should_enqueue = False
        return active_job, False

    defaults = {
        "title": snapshot["title"][:180],
        "headline": snapshot["headline"][:180],
        "ticker_label": snapshot["ticker_label"][:60],
        "ticker_text": snapshot["ticker_text"],
        "lower_third_label": snapshot["lower_third_label"][:60],
        "render_format": snapshot["render_format"],
        "frame_category": snapshot["frame_category"],
        "frame_template": snapshot["frame_template"],
        "source_video": video,
        "live_channel": channel,
        "playlist_item": playlist_item,
        "broadcast_session_id": broadcast_session_id,
        "snapshot": snapshot,
        "duration_seconds": video.effective_duration_seconds,
        "status": SocialRenderedVideo.Status.PENDING,
        "progress_percent": 0,
        "error_message": "",
        "is_active": True,
        "is_downloadable": True,
    }
    job, created = SocialRenderedVideo.objects.get_or_create(render_key=render_key, defaults=defaults)
    should_enqueue = created
    if not created and job.status == SocialRenderedVideo.Status.FAILED:
        for field, value in defaults.items():
            setattr(job, field, value)
        job.retry_count += 1
        job.save()
        should_enqueue = True
    elif (
        not created
        and job.status == SocialRenderedVideo.Status.PENDING
        and not job.rendered_video
        and job.updated_at < timezone.now() - timedelta(seconds=30)
    ):
        job.snapshot = snapshot
        job.error_message = ""
        job.progress_percent = 0
        job.save(update_fields=["snapshot", "error_message", "progress_percent", "updated_at"])
        should_enqueue = True
    elif (
        not created
        and job.status == SocialRenderedVideo.Status.PROCESSING
        and not job.rendered_video
        and (not job.started_at or job.updated_at < timezone.now() - timedelta(minutes=10))
    ):
        job.status = SocialRenderedVideo.Status.PENDING
        job.snapshot = snapshot
        job.error_message = "Render was stale and has been re-queued."
        job.progress_percent = 0
        job.retry_count += 1
        job.save(update_fields=["status", "snapshot", "error_message", "progress_percent", "retry_count", "updated_at"])
        should_enqueue = True
    job._render_should_enqueue = should_enqueue
    return job, created


def enqueue_broadcast_render_job_for_cycle_item(cycle_item):
    try:
        job, created = create_broadcast_render_job(cycle_item)
        if not job:
            return None
        if getattr(job, "_render_should_enqueue", created):
            queue_broadcast_render_task(job.pk)
        return job.pk
    except Exception:
        logger.exception("Failed to enqueue live broadcast render job for cycle item %s", getattr(cycle_item, "pk", None))
        return None


def enqueue_broadcast_render_jobs_for_cycle(cycle_id):
    try:
        items = list(LiveTVPlaylistCycleItem.objects.filter(cycle_id=cycle_id).order_by("position", "pk"))
        job_ids = []
        for cycle_item in items:
            job, created = create_broadcast_render_job(cycle_item)
            if job and getattr(job, "_render_should_enqueue", created):
                job_ids.append(job.pk)
        if not job_ids:
            return []
        for job_id in job_ids:
            queue_broadcast_render_task(job_id)
        return job_ids
    except Exception:
        logger.exception("Failed to enqueue live broadcast render jobs for cycle %s", cycle_id)
        return []


def enqueue_completed_broadcast_renders(channel, at=None, state=None):
    at = at or timezone.now()
    state = state or calculate_current_playback(channel, at=at)
    if not state:
        return []
    cycle = state["cycle"]
    if not cycle or cycle.total_duration_seconds <= 0:
        return []

    elapsed = max(0.0, (at - cycle.starts_at).total_seconds())
    if elapsed <= 0:
        return []

    completed_window = cycle.total_duration_seconds if channel.loop_enabled and elapsed >= cycle.total_duration_seconds else elapsed
    entries = list(cycle.items.select_related("video", "playlist_item").order_by("position", "pk"))
    completed_ids = []
    cursor = 0.0
    for entry in entries:
        cursor += entry.duration_seconds
        if cursor <= completed_window:
            completed_ids.append(entry.pk)

    if not completed_ids:
        return []

    active_cutoff = at - timedelta(seconds=30)
    processing_cutoff = at - timedelta(minutes=10)
    active_job = SocialRenderedVideo.objects.filter(
        live_channel=channel,
        frame_category="live_broadcast",
    ).filter(
        Q(status=SocialRenderedVideo.Status.PENDING, updated_at__gte=active_cutoff)
        | Q(status=SocialRenderedVideo.Status.PROCESSING, updated_at__gte=processing_cutoff)
    ).order_by("created_at").first()
    if active_job:
        return [active_job.pk]

    for entry in entries:
        if entry.pk not in completed_ids:
            continue
        try:
            job, created = create_broadcast_render_job(entry)
        except Exception:
            logger.exception("Failed to create live broadcast render job for cycle item %s", getattr(entry, "pk", None))
            continue
        if not job:
            continue
        if job.status in {SocialRenderedVideo.Status.COMPLETED, SocialRenderedVideo.Status.DONE} and job.rendered_video:
            continue
        if getattr(job, "_render_should_enqueue", created):
            queue_broadcast_render_task(job.pk)
        return [job.pk]
    return []


def recover_stale_render_jobs(at=None):
    """Requeue one orphaned render without competing with a healthy active render."""
    at = at or timezone.now()
    processing_cutoff = at - timedelta(minutes=10)
    pending_cutoff = at - timedelta(seconds=30)

    healthy_processing_exists = SocialRenderedVideo.objects.filter(
        status=SocialRenderedVideo.Status.PROCESSING,
        rendered_video="",
        updated_at__gte=processing_cutoff,
    ).exists()
    if healthy_processing_exists:
        return []

    job = (
        SocialRenderedVideo.objects.filter(
            Q(status=SocialRenderedVideo.Status.PROCESSING, updated_at__lt=processing_cutoff)
            | Q(status=SocialRenderedVideo.Status.PENDING, updated_at__lt=pending_cutoff),
            rendered_video="",
            is_active=True,
        )
        .order_by("created_at", "pk")
        .first()
    )
    if not job:
        return []

    was_processing = job.status == SocialRenderedVideo.Status.PROCESSING
    job.status = SocialRenderedVideo.Status.PENDING
    job.progress_percent = 0
    job.started_at = None
    job.error_message = "Stale render recovered and queued by health watchdog."
    if was_processing:
        job.retry_count += 1
    job.save(
        update_fields=[
            "status",
            "progress_percent",
            "started_at",
            "error_message",
            "retry_count",
            "updated_at",
        ]
    )
    queue_broadcast_render_task(job.pk)
    return [job.pk]


def ensure_current_cycle(channel, at=None):
    at = at or timezone.now()
    expire_old_live_playlist_items(channel, at=at)
    cycle = (
        channel.playlist_cycles.filter(starts_at__lte=at, total_duration_seconds__gt=0)
        .prefetch_related("items__video")
        .order_by("-starts_at", "-version")
        .first()
    )
    if cycle:
        return cycle
    with transaction.atomic():
        channel = LiveTVChannel.objects.select_for_update().get(pk=channel.pk)
        cycle = (
            channel.playlist_cycles.filter(starts_at__lte=at, total_duration_seconds__gt=0)
            .prefetch_related("items__video")
            .order_by("-starts_at", "-version")
            .first()
        )
        if cycle:
            return cycle
        items = list(
            channel.playlist_items.filter(is_active=True, duration_seconds__gt=0, video__created_at__gte=live_playlist_cutoff(at), video__hls_status=LiveTVChannel.HLSStatus.COMPLETED, video__hls_master_url__gt="")
            .select_related("video")
            .order_by("position", "pk")
        )
        if not items:
            return None
        started_at = channel.playback_started_at or at
        if started_at > at:
            started_at = at
        cycle = _create_cycle(channel, items, started_at, channel.playlist_version)
        if not channel.playback_started_at:
            channel.playback_started_at = started_at
            channel.save(update_fields=["playback_started_at", "updated_at"])
        return cycle


def calculate_current_playback(channel, at=None):
    at = at or timezone.now()
    cycle = ensure_current_cycle(channel, at=at)
    if not cycle or cycle.total_duration_seconds <= 0:
        return None
    entries = list(cycle.items.select_related("video", "playlist_item").order_by("position", "pk"))
    if not entries:
        return None
    elapsed = max(0.0, (at - cycle.starts_at).total_seconds())
    if not channel.loop_enabled and elapsed >= cycle.total_duration_seconds:
        return None
    offset = elapsed % cycle.total_duration_seconds if channel.loop_enabled else elapsed
    cursor = 0.0
    current_index = 0
    for index, entry in enumerate(entries):
        end = cursor + entry.duration_seconds
        if offset < end or index == len(entries) - 1:
            current_index = index
            break
        cursor = end
    current = entries[current_index]
    seek_position = max(0.0, min(offset - cursor, max(current.duration_seconds - 0.001, 0)))
    next_entry = entries[(current_index + 1) % len(entries)] if channel.loop_enabled or current_index + 1 < len(entries) else None
    return {
        "cycle": cycle,
        "entry": current,
        "video": current.video,
        "seek_position": seek_position,
        "video_started_at": at - timedelta(seconds=seek_position),
        "remaining_seconds": max(0.0, current.duration_seconds - seek_position),
        "next_entry": next_entry,
        "playlist_total_duration": cycle.total_duration_seconds,
        "playlist_version": cycle.version,
    }


def _rotate_after(items, playlist_item_id):
    if not items or not playlist_item_id:
        return items
    for index, item in enumerate(items):
        if item.pk == playlist_item_id:
            return items[index + 1 :] + items[: index + 1]
    return items


def _schedule_updated_cycle(channel, current_state, priority, selected_item=None, at=None):
    at = at or timezone.now()
    expire_old_live_playlist_items(channel, at=at)
    items = list(
        channel.playlist_items.filter(is_active=True, duration_seconds__gt=0, video__created_at__gte=live_playlist_cutoff(at), video__hls_status=LiveTVChannel.HLSStatus.COMPLETED, video__hls_master_url__gt="")
        .select_related("video")
        .order_by("position", "pk")
    )
    if not items:
        return None
    if priority == LiveTVPlaylistItem.Priority.IMMEDIATE and selected_item:
        items = [selected_item] + [item for item in items if item.pk != selected_item.pk]
        starts_at = at
        channel.playback_started_at = at
    else:
        current_item_id = current_state["entry"].playlist_item_id if current_state else None
        items = _rotate_after(items, current_item_id)
        if priority == LiveTVPlaylistItem.Priority.NEXT and selected_item:
            items = [selected_item] + [item for item in items if item.pk != selected_item.pk]
        starts_at = at + timedelta(seconds=current_state["remaining_seconds"]) if current_state else at
        if not channel.playback_started_at:
            channel.playback_started_at = at
    channel.playlist_cycles.filter(starts_at__gt=at).delete()
    cycle = _create_cycle(channel, items, starts_at, channel.playlist_version)
    channel.last_playlist_update = at
    channel.save(
        update_fields=["playlist_version", "last_playlist_update", "playback_started_at", "updated_at"]
    )
    return cycle


def _trim_playlist(channel, protected_item_ids=None, at=None):
    at = at or timezone.now()
    protected_item_ids = set(protected_item_ids or [])
    expire_old_live_playlist_items(channel, at=at)
    items = list(channel.playlist_items.filter(is_active=True, video__created_at__gte=live_playlist_cutoff(at), video__hls_status=LiveTVChannel.HLSStatus.COMPLETED, video__hls_master_url__gt="").order_by("added_at", "pk"))
    target = max(1, int(channel.target_playlist_duration_seconds or 10800))
    total = sum(item.duration_seconds for item in items)
    while total > target and len(items) > 1:
        candidate = next((item for item in items if item.pk not in protected_item_ids), None)
        if not candidate:
            break
        candidate.is_active = False
        candidate.removed_at = at
        candidate.save(update_fields=["is_active", "removed_at", "updated_at"])
        items.remove(candidate)
        total -= candidate.duration_seconds


def add_uploaded_video_to_live_playlist(video, channel=None, priority=LiveTVPlaylistItem.Priority.NORMAL):
    validate_playlist_video(video)
    if priority not in LiveTVPlaylistItem.Priority.values:
        raise ValidationError({"priority": "Invalid playlist priority."})
    channel = channel or get_main_live_channel(create=False)
    if not channel:
        raise ValidationError("Main auto live playlist channel is not configured.")
    if channel.pk == video.pk:
        raise ValidationError("Main channel cannot reference itself.")

    with transaction.atomic():
        now = timezone.now()
        channel = LiveTVChannel.objects.select_for_update().get(pk=channel.pk)
        video = LiveTVChannel.objects.select_for_update().get(pk=video.pk)
        validate_playlist_video(video)
        current_state = calculate_current_playback(channel, at=now)
        item = LiveTVPlaylistItem.objects.select_for_update().filter(channel=channel, video=video).first()
        if item and item.is_active and priority == LiveTVPlaylistItem.Priority.NORMAL:
            return item, False
        expire_old_live_playlist_items(channel, at=now)
        max_position = channel.playlist_items.filter(is_active=True, video__created_at__gte=live_playlist_cutoff(now), video__hls_status=LiveTVChannel.HLSStatus.COMPLETED, video__hls_master_url__gt="").aggregate(value=Max("position"))["value"]
        if item:
            item.is_active = True
            item.removed_at = None
            item.duration_seconds = video.effective_duration_seconds
            item.priority = priority
            item.position = (max_position + 1) if max_position is not None else 0
            item.full_clean()
            item.save()
            created = False
        else:
            item = LiveTVPlaylistItem(
                channel=channel,
                video=video,
                position=(max_position + 1) if max_position is not None else 0,
                duration_seconds=video.effective_duration_seconds,
                priority=priority,
            )
            item.full_clean()
            item.save()
            created = True
        protected = {item.pk}
        if current_state:
            protected.add(current_state["entry"].playlist_item_id)
        _trim_playlist(channel, protected_item_ids=protected, at=now)
        normalize_playlist_positions(channel)
        item.refresh_from_db()
        channel.playlist_version += 1
        _schedule_updated_cycle(channel, current_state, priority, selected_item=item, at=now)
        return item, created


def update_playlist_item(item, action):
    if action not in {"move_up", "move_down", "remove", "restore", "next", "immediate"}:
        raise ValidationError("Unknown playlist action.")
    if action == "restore":
        return add_uploaded_video_to_live_playlist(item.video, item.channel)[0]
    with transaction.atomic():
        now = timezone.now()
        channel = LiveTVChannel.objects.select_for_update().get(pk=item.channel_id)
        item = LiveTVPlaylistItem.objects.select_for_update().select_related("video").get(pk=item.pk)
        current_state = calculate_current_playback(channel, at=now)
        expire_old_live_playlist_items(channel, at=now)
        active_items = list(channel.playlist_items.select_for_update().filter(is_active=True, video__created_at__gte=live_playlist_cutoff(now), video__hls_status=LiveTVChannel.HLSStatus.COMPLETED, video__hls_master_url__gt="").order_by("position", "pk"))
        if action == "remove":
            if len(active_items) <= 1:
                raise ValidationError("At least one playable item must remain active.")
            item.is_active = False
            item.removed_at = now
            item.save(update_fields=["is_active", "removed_at", "updated_at"])
            priority = LiveTVPlaylistItem.Priority.NORMAL
        elif action in {"move_up", "move_down"}:
            index = next((i for i, value in enumerate(active_items) if value.pk == item.pk), None)
            step = -1 if action == "move_up" else 1
            other_index = index + step if index is not None else -1
            if 0 <= other_index < len(active_items):
                other = active_items[other_index]
                item.position, other.position = other.position, item.position
                LiveTVPlaylistItem.objects.bulk_update([item, other], ["position", "updated_at"])
            priority = LiveTVPlaylistItem.Priority.NORMAL
        else:
            priority = LiveTVPlaylistItem.Priority.NEXT if action == "next" else LiveTVPlaylistItem.Priority.IMMEDIATE
            item.priority = priority
            item.save(update_fields=["priority", "updated_at"])
        normalize_playlist_positions(channel)
        channel.playlist_version += 1
        _schedule_updated_cycle(channel, current_state, priority, selected_item=item, at=now)
        return item


def deactivate_unstreamable_playlist_items(channel, at=None):
    if not channel or not channel.pk:
        return 0
    at = at or timezone.now()
    items = list(
        channel.playlist_items.select_related("video")
        .filter(is_active=True)
        .order_by("position", "pk")
    )
    remove_ids = [
        item.pk
        for item in items
        if not live_playlist_video_is_streamable(item.video, at=at) or item.duration_seconds <= 0
    ]
    if not remove_ids:
        return 0
    LiveTVPlaylistItem.objects.filter(pk__in=remove_ids).update(is_active=False, removed_at=at, updated_at=at)
    normalize_playlist_positions(channel)
    channel.playlist_version += 1
    channel.last_playlist_update = at
    channel.playlist_cycles.all().delete()
    if not channel.playlist_items.filter(
        is_active=True,
        duration_seconds__gt=0,
        video__hls_status=LiveTVChannel.HLSStatus.COMPLETED,
        video__hls_master_url__gt="",
    ).exists():
        channel.playback_started_at = None
    channel.save(update_fields=["playlist_version", "last_playlist_update", "playback_started_at", "updated_at"])
    return len(remove_ids)


def repair_live_tv_health(queue_hls=True, queue_renders=True, at=None):
    """Find stuck/missing Live TV work and move it toward HLS-ready playback/rendering."""
    at = at or timezone.now()
    channel = get_main_live_channel(create=True)
    report = {
        "expired_playlist_items": expire_old_live_playlist_items(channel, at=at),
        "removed_unstreamable_items": deactivate_unstreamable_playlist_items(channel, at=at),
        "hls_queued": 0,
        "playlist_added": 0,
        "renders_queued": 0,
        "stale_renders_queued": 0,
    }
    stale_cutoff = at - timedelta(minutes=getattr(settings, "LIVE_TV_HLS_PROCESSING_STALE_MINUTES", 20))
    failed_retry_cutoff = at - timedelta(minutes=getattr(settings, "LIVE_TV_HLS_FAILED_RETRY_MINUTES", 10))
    candidates = LiveTVChannel.objects.filter(
        source_type=LiveTVChannel.SourceType.DIRECT,
        auto_add_to_live=True,
        is_active=True,
        video_file__isnull=False,
        created_at__gte=live_playlist_cutoff(at),
    ).exclude(pk=channel.pk)

    if queue_hls:
        for video in candidates.order_by("created_at", "pk")[:100]:
            processing_is_fresh = (
                video.hls_status == LiveTVChannel.HLSStatus.PROCESSING
                and video.updated_at
                and video.updated_at >= stale_cutoff
            )
            failed_retry_is_too_soon = (
                video.hls_status == LiveTVChannel.HLSStatus.FAILED
                and video.updated_at
                and video.updated_at >= failed_retry_cutoff
            )
            needs_hls = (
                video.hls_status in {LiveTVChannel.HLSStatus.PENDING, LiveTVChannel.HLSStatus.FAILED}
                or not live_video_hls_ready(video)
                or video.effective_duration_seconds <= 0
            )
            if processing_is_fresh or failed_retry_is_too_soon or not needs_hls:
                continue
            try:
                from .views import enqueue_live_channel_hls_job

                if video.hls_status != LiveTVChannel.HLSStatus.PENDING:
                    LiveTVChannel.objects.filter(pk=video.pk).update(
                        hls_status=LiveTVChannel.HLSStatus.PENDING,
                        hls_progress_percent=0,
                        processing_error="Queued by Live TV health repair.",
                        updated_at=timezone.now(),
                    )
                enqueue_live_channel_hls_job(video.pk)
                report["hls_queued"] += 1
                # HLS is intentionally serial. The task queues the next pending
                # upload when it finishes, so one seed job is sufficient.
                break
            except Exception:
                logger.exception("Failed to queue HLS repair for video %s", video.pk)

    ready_videos = list(candidates.filter(
        hls_status=LiveTVChannel.HLSStatus.COMPLETED,
        hls_master_url__gt="",
        duration_seconds__gt=0,
    ).order_by("display_order", "created_at", "pk"))
    for video in ready_videos:
        if channel.playlist_items.filter(video=video, is_active=True).exists():
            continue
        try:
            add_uploaded_video_to_live_playlist(video, channel=channel)
            report["playlist_added"] += 1
        except ValidationError:
            logger.exception("HLS-ready video %s could not be added to live playlist.", video.pk)

    if report["playlist_added"] or report["removed_unstreamable_items"] or report["expired_playlist_items"]:
        channel.refresh_from_db()
        ensure_current_cycle(channel, at=at)

    if queue_renders:
        report["stale_renders_queued"] = len(recover_stale_render_jobs(at=at))
        state = calculate_current_playback(channel, at=at)
        report["renders_queued"] = len(enqueue_completed_broadcast_renders(channel, at=at, state=state))
    return report


def rebuild_live_playlist(videos, channel=None):
    channel = channel or get_main_live_channel(create=True)
    with transaction.atomic():
        now = timezone.now()
        channel = LiveTVChannel.objects.select_for_update().get(pk=channel.pk)
        channel.playlist_items.filter(is_active=True).update(is_active=False, removed_at=now)
        position = 0
        for video in videos:
            try:
                validate_playlist_video(video)
            except ValidationError:
                continue
            item, _created = LiveTVPlaylistItem.objects.update_or_create(
                channel=channel,
                video=video,
                defaults={
                    "position": position,
                    "duration_seconds": video.effective_duration_seconds,
                    "priority": LiveTVPlaylistItem.Priority.NORMAL,
                    "is_active": True,
                    "removed_at": None,
                },
            )
            position += 1
        items = normalize_playlist_positions(channel)
        channel.playlist_version += 1
        channel.playback_started_at = now if items else None
        channel.last_playlist_update = now
        channel.playlist_cycles.all().delete()
        if items:
            _create_cycle(channel, items, now, channel.playlist_version)
        channel.save(
            update_fields=["playlist_version", "playback_started_at", "last_playlist_update", "updated_at"]
        )
    return channel
