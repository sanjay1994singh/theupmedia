import ipaddress
import socket
from urllib.parse import urlparse

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone


BLOCKED_HOSTS = {"localhost", "ip6-localhost", "ip6-loopback"}
BLOCKED_IPS = {
    ipaddress.ip_address("169.254.169.254"),
    ipaddress.ip_address("100.100.100.200"),
}


def validate_public_media_url(url):
    if not url or len(url) > 2000:
        raise ValidationError("Valid URL required.")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValidationError("Only http and https URLs are supported.")
    if not parsed.hostname:
        raise ValidationError("URL host is missing.")

    host = parsed.hostname.strip().lower().rstrip(".")
    if host in BLOCKED_HOSTS:
        raise ValidationError("Local/private URLs are not allowed.")

    try:
        addresses = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise ValidationError("URL host could not be verified.") from exc

    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if (
            ip in BLOCKED_IPS
            or ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise ValidationError("Private/internal network URLs are not allowed.")
    return url


def enforce_job_limits(user):
    from social_downloader.models import SocialMediaDownload

    active = SocialMediaDownload.objects.filter(
        user=user,
        status__in=[SocialMediaDownload.Status.PENDING, SocialMediaDownload.Status.PROCESSING],
    ).count()
    max_concurrent = int(getattr(settings, "SOCIAL_DOWNLOADER_MAX_CONCURRENT_JOBS", 1))
    if active >= max_concurrent:
        raise ValidationError(f"Only {max_concurrent} active download job allowed at a time.")

    daily_limit = int(getattr(settings, "SOCIAL_DOWNLOADER_DAILY_USER_LIMIT", 20))
    since = timezone.now() - timezone.timedelta(days=1)
    created_today = SocialMediaDownload.objects.filter(user=user, created_at__gte=since).count()
    if created_today >= daily_limit:
        raise ValidationError(f"Daily download limit reached. Maximum {daily_limit} jobs allowed per 24 hours.")
