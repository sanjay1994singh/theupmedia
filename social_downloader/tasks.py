from celery import shared_task

from .services.downloader import run_download_job


@shared_task(name="social_downloader.run_download")
def run_social_download_task(job_id):
    run_download_job(job_id)

