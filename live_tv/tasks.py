from celery import shared_task

from .views import run_media_download_job, run_social_render_job


@shared_task(name="live_tv.render_social_video")
def render_social_video_task(job_id):
    run_social_render_job(job_id)


@shared_task(name="live_tv.download_media")
def download_media_task(job_id):
    run_media_download_job(job_id)
