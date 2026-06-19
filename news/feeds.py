from django.contrib.syndication.views import Feed
from django.urls import reverse

from .models import Article


class LatestNewsFeed(Feed):
    title = "The Up Media Latest News"
    link = "/news/"
    description = "Latest news and updates from The Up Media."

    def items(self):
        return Article.published.select_related("category")[:30]

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return item.summary

    def item_link(self, item):
        return reverse("news:article_detail", kwargs={"slug": item.slug})
