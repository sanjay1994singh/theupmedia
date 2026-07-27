from django.conf import settings
from django.db.models import Count, Q

from news.models import Category


def site_settings(request):
    return {
        "SITE_NAME": settings.SITE_NAME,
        "SITE_DOMAIN": settings.SITE_DOMAIN,
        "NAV_CATEGORIES": Category.objects.filter(is_active=True)
        .annotate(published_count=Count("articles", filter=Q(articles__status="published")))
        .filter(published_count__gt=0)[:8],
    }
