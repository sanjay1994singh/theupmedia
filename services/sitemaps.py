from django.contrib.sitemaps import Sitemap

from .models import Service


class ServiceSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.85
    protocol = "https"

    def items(self):
        return Service.objects.filter(is_active=True)

    def lastmod(self, obj):
        return obj.updated_at
