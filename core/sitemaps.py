from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticPageSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.5
    protocol = "https"

    def items(self):
        return [
            "core:about",
            "core:contact",
            "core:privacy_policy",
            "core:terms",
            "core:disclaimer",
            "blog:post_list",
            "services:service_list",
        ]

    def location(self, item):
        return reverse(item)
