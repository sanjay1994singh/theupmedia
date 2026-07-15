from django.conf import settings
from django.contrib.sitemaps.views import sitemap
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.html import escape
from django.utils import timezone
from types import SimpleNamespace

from news.feeds import LatestNewsFeed
from news.models import Article, Category
from news.sitemaps import ArticleSitemap, CategorySitemap, CitySitemap, StateSitemap
from blog.models import BlogPost
from blog.sitemaps import BlogPostSitemap
from services.models import Service
from services.sitemaps import ServiceSitemap
from subscriptions.models import SubscriptionPlan
from live_tv.models import LiveTVChannel, LiveTVSetting
from .sitemaps import StaticPageSitemap


def home(request):
    featured = Article.published.select_related("category", "state", "city", "author").filter(is_featured=True)[:5]
    latest = Article.published.select_related("category", "state", "city", "author")[:12]
    categories = Category.objects.filter(is_active=True)[:8]
    latest_blogs = BlogPost.published.select_related("author")[:3]
    services = Service.objects.filter(is_active=True, is_featured=True)[:6]
    subscription_plans = list(SubscriptionPlan.objects.select_related("service").filter(is_active=True, service__is_active=True)[:6])
    for plan in subscription_plans:
        plan.home_features = [feature.strip() for feature in plan.features.splitlines() if feature.strip()][:3]
    home_live_tv_channels = list(LiveTVChannel.objects.filter(is_active=True))
    home_live_tv = home_live_tv_channels[0] if home_live_tv_channels else None
    home_live_tv_next = None
    home_live_settings = LiveTVSetting.get_solo()
    home_news_ticker = SimpleNamespace(
        label=home_live_settings.default_ticker_label,
        text=home_live_settings.default_ticker_text,
        speed_seconds=home_live_settings.ticker_speed_seconds,
        mobile_speed_seconds=home_live_settings.mobile_ticker_speed_seconds,
        style="red_white_slant",
        updated_at=home_live_settings.updated_at,
    )
    if home_live_tv_channels:
        home_live_tv_next = home_live_tv_channels[1] if len(home_live_tv_channels) > 1 else home_live_tv
    return render(
        request,
        "core/home.html",
        {
            "featured": featured,
            "latest": latest,
            "categories": categories,
            "latest_blogs": latest_blogs,
            "business_services": services,
            "subscription_plans": subscription_plans,
            "home_live_tv": home_live_tv,
            "home_live_tv_next": home_live_tv_next,
            "home_live_tv_loop_same": bool(home_live_tv and home_live_tv_next and home_live_tv.pk == home_live_tv_next.pk),
            "home_live_settings": home_live_settings,
            "home_news_ticker": home_news_ticker,
        },
    )


def about(request):
    return render(request, "core/about.html")


def contact(request):
    return render(request, "core/contact.html")


def privacy_policy(request):
    return render(request, "core/privacy_policy.html")


def terms(request):
    return render(request, "core/terms.html")


def disclaimer(request):
    return render(request, "core/disclaimer.html")


def robots_txt(request):
    lines = [
        "User-agent: *",
        "Allow: /",
        f"Sitemap: {settings.SITE_DOMAIN}{reverse('core:sitemap')}",
        f"Sitemap: {settings.SITE_DOMAIN}{reverse('core:news_sitemap')}",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def sitemap_xml(request):
    return sitemap(
        request,
        {
            "articles": ArticleSitemap,
            "categories": CategorySitemap,
            "states": StateSitemap,
            "cities": CitySitemap,
            "blog": BlogPostSitemap,
            "services": ServiceSitemap,
            "pages": StaticPageSitemap,
        },
    )


def news_sitemap_xml(request):
    articles = Article.published.select_related("category", "state", "city")[:1000]
    xml_items = []
    for article in articles:
        xml_items.append(
            f"""
  <url>
    <loc>{settings.SITE_DOMAIN}{article.get_absolute_url()}</loc>
    <news:news>
      <news:publication>
        <news:name>{settings.SITE_NAME}</news:name>
        <news:language>en</news:language>
      </news:publication>
      <news:publication_date>{article.published_at.date().isoformat()}</news:publication_date>
      <news:title>{escape(article.title)}</news:title>
    </news:news>
    <lastmod>{article.updated_at.isoformat()}</lastmod>
  </url>"""
        )
    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
{''.join(xml_items)}
</urlset>"""
    return HttpResponse(content, content_type="application/xml")


def rss_xml(request):
    return LatestNewsFeed()(request)


def health(request):
    return HttpResponse(f"ok {timezone.now().isoformat()}", content_type="text/plain")
