from django.contrib.sitemaps import Sitemap

from .models import Article, Category, City, State


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


class StateSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.75
    protocol = "https"

    def items(self):
        return State.objects.filter(is_active=True)


class CitySitemap(Sitemap):
    changefreq = "daily"
    priority = 0.72
    protocol = "https"

    def items(self):
        return City.objects.filter(is_active=True, state__is_active=True).select_related("state")
