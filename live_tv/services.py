import logging
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from .models import (
    LiveTVChannel,
    LiveTVPlaylistCycle,
    LiveTVPlaylistCycleItem,
    LiveTVPlaylistItem,
    LiveTVSetting,
    NewsTickerSetting,
    SocialRenderedVideo,
)

logger = logging.getLogger(__name__)


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


def broadcast_snapshot_for(video, channel, playlist_item, cycle_item):
    setting = LiveTVSetting.get_solo()
    ticker = NewsTickerSetting.get_solo()
    headline = video.headline or ""
    lower_label = video.lower_third_label or ""
    title = headline or video.title or f"{channel.title} {timezone.localtime().strftime('%Y-%m-%d %H:%M')}"
    return {
        "title": title,
        "headline": headline,
        "headline_label": lower_label,
        "lower_third_label": lower_label,
        "ticker_label": ticker.label or setting.default_ticker_label,
        "ticker_text": ticker.text or setting.default_ticker_text,
        "ticker_speed_seconds": ticker.speed_seconds,
        "mobile_ticker_speed_seconds": ticker.mobile_speed_seconds,
        "ticker_style": ticker.style,
        "channel_name": setting.name,
        "channel_logo": setting.channel_logo.name if setting.channel_logo else "",
        "live_label": setting.live_label,
        "show_channel_logo": setting.show_channel_logo,
        "show_live_badge": setting.show_live_badge,
        "show_lower_third": setting.show_lower_third,
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
    if not video.video_file:
        return None, False
    broadcast_session_id = f"cycle-{cycle_item.cycle_id}-v{cycle_item.cycle.version}-item-{cycle_item.pk}"
    render_key = f"live:{channel.pk}:{cycle_item.playlist_item_id}:{video.pk}:{broadcast_session_id}"
    snapshot = broadcast_snapshot_for(video, channel, cycle_item.playlist_item, cycle_item)
    defaults = {
        "title": snapshot["title"][:180],
        "headline": snapshot["headline"][:180],
        "ticker_label": snapshot["ticker_label"][:60],
        "ticker_text": snapshot["ticker_text"][:260],
        "lower_third_label": snapshot["lower_third_label"][:60],
        "render_format": snapshot["render_format"],
        "frame_category": snapshot["frame_category"],
        "frame_template": snapshot["frame_template"],
        "source_video": video,
        "live_channel": channel,
        "playlist_item": cycle_item.playlist_item,
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
    job._render_should_enqueue = should_enqueue
    return job, created


def enqueue_broadcast_render_job_for_cycle_item(cycle_item):
    try:
        job, created = create_broadcast_render_job(cycle_item)
        if not job:
            return None
        if getattr(job, "_render_should_enqueue", created):
            from .tasks import render_live_broadcast_video_task

            render_live_broadcast_video_task.delay(job.pk)
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
        from .tasks import render_live_broadcast_video_task

        for job_id in job_ids:
            render_live_broadcast_video_task.delay(job_id)
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

    jobs = []
    for entry in entries:
        if entry.pk not in completed_ids:
            continue
        job_id = enqueue_broadcast_render_job_for_cycle_item(entry)
        if job_id:
            jobs.append(job_id)
    return jobs


def ensure_current_cycle(channel, at=None):
    at = at or timezone.now()
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
            channel.playlist_items.filter(is_active=True, duration_seconds__gt=0)
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
    items = list(
        channel.playlist_items.filter(is_active=True, duration_seconds__gt=0)
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
    items = list(channel.playlist_items.filter(is_active=True).order_by("added_at", "pk"))
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
        max_position = channel.playlist_items.filter(is_active=True).aggregate(value=Max("position"))["value"]
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
        active_items = list(channel.playlist_items.select_for_update().filter(is_active=True).order_by("position", "pk"))
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
