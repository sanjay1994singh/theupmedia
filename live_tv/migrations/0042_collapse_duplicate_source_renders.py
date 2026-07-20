from django.db import migrations
from django.utils import timezone


def collapse_duplicate_source_renders(apps, schema_editor):
    SocialRenderedVideo = apps.get_model("live_tv", "SocialRenderedVideo")
    source_ids = (
        SocialRenderedVideo.objects.filter(
            source_video_id__isnull=False,
            frame_category="live_broadcast",
            frame_template="broadcast_live_tv",
            is_active=True,
        )
        .values_list("source_video_id", flat=True)
        .distinct()
    )
    for source_id in source_ids.iterator():
        jobs = list(
            SocialRenderedVideo.objects.filter(
                source_video_id=source_id,
                frame_category="live_broadcast",
                frame_template="broadcast_live_tv",
                is_active=True,
            ).order_by("completed_at", "created_at", "pk")
        )
        completed = [
            job for job in jobs
            if job.status in {"completed", "done"} and bool(job.rendered_video)
        ]
        canonical = completed[0] if completed else (jobs[0] if jobs else None)
        if not canonical:
            continue
        now = timezone.now()
        for job in jobs:
            if job.pk == canonical.pk:
                continue
            job.status = "done"
            job.progress_percent = 100
            job.is_active = False
            job.error_message = f"Duplicate hidden. Canonical render id: {canonical.pk}"
            job.completed_at = job.completed_at or now
            job.save(
                update_fields=[
                    "status",
                    "progress_percent",
                    "is_active",
                    "error_message",
                    "completed_at",
                    "updated_at",
                ]
            )


class Migration(migrations.Migration):

    dependencies = [
        ("live_tv", "0041_livetvsetting_badge_sizes"),
    ]

    operations = [
        migrations.RunPython(collapse_duplicate_source_renders, migrations.RunPython.noop),
    ]
