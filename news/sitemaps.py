from django.contrib.sitemaps import Sitemap

from .models import Article, Category


class ArticleSitemap(Sitemap):
    changefreq = "hourly"
    priority = 0.9
    protocol = "https"

    def items(self):
        return Article.published.all()

    def lastmod(self, obj):
        return obj.updated_at


class CategorySitemap(Sitemap):
    changefreq = "daily"
    priority = 0.7
    protocol = "https"

    def items(self):
        return Category.objects.filter(is_active=True)
