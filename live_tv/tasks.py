from celery import shared_task

from .hls import convert_live_channel_to_hls, convert_short_to_hls
from .views import run_media_download_job, run_social_render_job


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


@shared_task(name="live_tv.process_live_channel_hls")
def process_live_channel_hls_task(channel_id):
    convert_live_channel_to_hls(channel_id)


@shared_task(name="live_tv.cleanup_rendered_video_temps")
def cleanup_rendered_video_temps_task(hours=24):
    from django.core.management import call_command

    call_command("cleanup_rendered_video_temps", hours=hours)
