from celery import shared_task

from .hls import convert_live_channel_to_hls, convert_short_to_hls
from .views import run_media_download_job, run_social_render_job


@shared_task(name="live_tv.render_social_video")
def render_social_video_task(job_id):
    run_social_render_job(job_id)


@shared_task(name="live_tv.download_media")
def download_media_task(job_id):
    run_media_download_job(job_id)


@shared_task(name="live_tv.process_short_hls")
def process_short_hls_task(short_id):
    convert_short_to_hls(short_id)


@shared_task(name="live_tv.process_live_channel_hls")
def process_live_channel_hls_task(channel_id):
    convert_live_channel_to_hls(channel_id)
