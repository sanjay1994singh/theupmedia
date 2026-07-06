from celery import shared_task

from .views import run_social_render_job


@shared_task(name="live_tv.render_social_video")
def render_social_video_task(job_id):
    run_social_render_job(job_id)
