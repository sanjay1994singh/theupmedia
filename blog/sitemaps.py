from django.contrib.sitemaps import Sitemap

from .models import BlogPost


class BlogPostSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8
    protocol = "https"

    def items(self):
        return BlogPost.published.all()

    def lastmod(self, obj):
        return obj.updated_at
