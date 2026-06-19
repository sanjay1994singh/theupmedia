from django.conf import settings

from news.models import Category


def site_settings(request):
    return {
        "SITE_NAME": settings.SITE_NAME,
        "SITE_DOMAIN": settings.SITE_DOMAIN,
        "NAV_CATEGORIES": Category.objects.filter(is_active=True)[:8],
    }
