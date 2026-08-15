import json

from django.conf import settings
from django.contrib.sitemaps.views import sitemap
from django.contrib import messages
from django.core.mail import send_mail
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.html import escape
from django.utils import timezone
from types import SimpleNamespace
from urllib.parse import quote

from news.feeds import LatestNewsFeed
from news.models import Article, Category
from news.sitemaps import ArticleSitemap, CategorySitemap, CitySitemap, StateSitemap
from blog.models import BlogPost
from blog.sitemaps import BlogPostSitemap
from services.models import Service
from services.sitemaps import ServiceSitemap
from subscriptions.models import SubscriptionPlan
from live_tv.models import LiveTVChannel, LiveTVSetting
from live_tv.services import calculate_current_playback, get_main_live_channel
from .forms import AccountDeletionRequestForm, ContactForm
from .sitemaps import StaticPageSitemap


def home(request):
    featured = Article.published.select_related("category", "state", "city", "author").filter(is_featured=True)[:5]
    latest = Article.published.select_related("category", "state", "city", "author")[:12]
    categories = (
        Category.objects
        .filter(is_active=True, articles__status=Article.Status.PUBLISHED)
        .distinct()[:8]
    )
    latest_blogs = BlogPost.published.select_related("author")[:3]
    services = Service.objects.filter(is_active=True, is_featured=True)[:6]
    subscription_plans = list(SubscriptionPlan.objects.select_related("service").filter(is_active=True, service__is_active=True)[:6])
    for plan in subscription_plans:
        plan.home_features = [feature.strip() for feature in plan.features.splitlines() if feature.strip()][:3]
    home_live_tv_channels = list(LiveTVChannel.objects.filter(is_active=True).order_by("display_order", "pk"))
    home_live_tv = get_main_live_channel(create=False) or next((channel for channel in home_live_tv_channels if channel.is_live), None) or (home_live_tv_channels[0] if home_live_tv_channels else None)
    home_live_tv_next = None
    home_live_seek_position = 0
    home_live_video_duration = 0
    home_live_server_time = timezone.now()
    home_live_settings = LiveTVSetting.get_solo()
    home_news_ticker = SimpleNamespace(
        label=home_live_settings.default_ticker_label,
        text=home_live_settings.default_ticker_text,
        speed_seconds=home_live_settings.ticker_speed_seconds,
        mobile_speed_seconds=home_live_settings.mobile_ticker_speed_seconds,
        style="red_white_slant",
        updated_at=home_live_settings.updated_at,
        started_at=home_live_settings.ticker_started_at,
        server_time=home_live_server_time,
        offset_seconds=max(0.0, (home_live_server_time - home_live_settings.ticker_started_at).total_seconds()),
        clock_key=f"live-tv-ticker-{home_live_settings.pk}-{home_live_settings.ticker_started_at.isoformat()}",
    )
    if home_live_tv and home_live_tv.source_type == LiveTVChannel.SourceType.PLAYLIST:
        playlist_state = calculate_current_playback(home_live_tv, at=home_live_server_time)
        if playlist_state:
            home_live_tv = playlist_state["video"]
            home_live_tv_next = playlist_state["next_entry"].video if playlist_state.get("next_entry") else home_live_tv
            home_live_seek_position = round(playlist_state["seek_position"], 3)
            home_live_video_duration = playlist_state["entry"].duration_seconds
    elif home_live_tv_channels:
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
            "home_live_seek_position": home_live_seek_position,
            "home_live_video_duration": home_live_video_duration,
            "home_live_server_time": home_live_server_time.isoformat(),
            "home_live_settings": home_live_settings,
            "home_news_ticker": home_news_ticker,
        },
    )


def about(request):
    return render(request, "core/about.html")


def contact(request):
    form = ContactForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if form.cleaned_data.get("website"):
            messages.success(request, "Thank you. Your message has been received.")
            form = ContactForm()
        else:
            try:
                send_mail(
                    subject=f"Website contact: {form.cleaned_data['subject']}",
                    message=(
                        f"Name: {form.cleaned_data['name']}\n"
                        f"Email: {form.cleaned_data['email']}\n\n"
                        f"{form.cleaned_data['message']}"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[settings.CONTACT_EMAIL],
                    fail_silently=False,
                )
                messages.success(request, "Thank you. Your message has been sent.")
                form = ContactForm()
            except Exception:
                messages.error(request, "Message could not be sent right now. Please email us directly.")
    return render(request, "core/contact.html", {"form": form})


def privacy_policy(request):
    return render(request, "core/privacy_policy.html")


def terms(request):
    return render(request, "core/terms.html")


def account_deletion(request):
    form = AccountDeletionRequestForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if form.cleaned_data.get("website"):
            messages.success(request, "Your deletion request has been received.")
            form = AccountDeletionRequestForm()
        else:
            try:
                send_mail(
                    subject="The UP Media app account deletion request",
                    message=(
                        f"Username: {form.cleaned_data['username']}\n"
                        f"Registered email: {form.cleaned_data['email']}\n\n"
                        f"Reason: {form.cleaned_data.get('reason') or 'Not provided'}"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[settings.CONTACT_EMAIL],
                    fail_silently=False,
                )
                messages.success(request, "Your deletion request has been submitted. We will verify and process it within 30 days.")
                form = AccountDeletionRequestForm()
            except Exception:
                messages.error(request, "Request could not be sent. Please email srbc500@gmail.com with subject 'Account deletion'.")
    return render(request, "core/account_deletion.html", {"form": form})


def disclaimer(request):
    return render(request, "core/disclaimer.html")


def editorial_policy(request):
    return render(request, "core/editorial_policy.html")


def fact_checking_policy(request):
    return render(request, "core/fact_checking_policy.html")


def corrections_policy(request):
    return render(request, "core/corrections_policy.html")


def robots_txt(request):
    lines = [
        "User-agent: *",
        "Allow: /",
        f"Sitemap: {settings.SITE_DOMAIN}{reverse('core:sitemap')}",
        f"Sitemap: {settings.SITE_DOMAIN}{reverse('core:news_sitemap')}",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def ads_txt(request):
    response = HttpResponse(
        "google.com, pub-2037181352494119, DIRECT, f08c47fec0942fa0\n",
        content_type="text/plain; charset=utf-8",
    )
    response["X-Content-Type-Options"] = "nosniff"
    return response


def assetlinks_json(request):
    fingerprints = getattr(settings, "ANDROID_APP_LINK_SHA256_CERT_FINGERPRINTS", [])
    packages = getattr(settings, "ANDROID_APP_LINK_PACKAGES", ["com.upmedia.livetv"])
    entries = [
        {
            "relation": ["delegate_permission/common.handle_all_urls"],
            "target": {
                "namespace": "android_app",
                "package_name": package,
                "sha256_cert_fingerprints": fingerprints,
            },
        }
        for package in packages
        if package and fingerprints
    ]
    response = HttpResponse(json.dumps(entries), content_type="application/json")
    response["Cache-Control"] = "public, max-age=3600"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def app_article_link(request, slug):
    article = get_object_or_404(Article.published.select_related("category"), slug=slug)
    encoded_slug = quote(article.slug, safe="")
    app_url = f"upmedia://article/{encoded_slug}"
    web_url = request.build_absolute_uri(article.get_absolute_url())
    share_image_url = request.build_absolute_uri(reverse("news:share_image", kwargs={"slug": article.slug}))
    share_image_url = f"{share_image_url}?v={int(article.updated_at.timestamp())}"
    description = article.meta_description or article.summary or article.title
    play_url = getattr(settings, "PLAY_STORE_APP_URL", "https://play.google.com/store/apps/details?id=com.upmedia.livetv")
    intent_url = (
        f"intent://article/{encoded_slug}"
        "#Intent;scheme=upmedia;package=com.upmedia.livetv;"
        f"S.browser_fallback_url={quote(play_url, safe='')};end"
    )
    android_redirect = ""
    if "android" in request.META.get("HTTP_USER_AGENT", "").lower():
        android_redirect = f"""
  <script>
    setTimeout(function () {{ window.location.href = "{escape(app_url)}"; }}, 150);
    setTimeout(function () {{ window.location.href = "{escape(intent_url)}"; }}, 1400);
  </script>"""
    html = f"""<!doctype html>
<html lang="hi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(article.title)} - The UP Media</title>
  <link rel="canonical" href="{escape(web_url)}">
  <meta name="description" content="{escape(description)}">
  <meta property="og:title" content="{escape(article.title)}">
  <meta property="og:description" content="{escape(description)}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{escape(request.build_absolute_uri(request.path))}">
  <meta property="og:image" content="{escape(share_image_url)}">
  <meta property="og:image:secure_url" content="{escape(share_image_url)}">
  <meta property="og:image:type" content="image/jpeg">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{escape(article.title)}">
  <meta name="twitter:description" content="{escape(description)}">
  <meta name="twitter:image" content="{escape(share_image_url)}">
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; background: #07111f; color: #fff; }}
    main {{ max-width: 560px; margin: 0 auto; padding: 40px 20px; }}
    h1 {{ font-size: 24px; line-height: 1.25; }}
    a {{ display: block; margin: 14px 0; padding: 14px 16px; border-radius: 10px; text-align: center; text-decoration: none; font-weight: 700; }}
    .primary {{ background: #e11d2e; color: #fff; }}
    .secondary {{ background: #14243a; color: #fff; border: 1px solid #2d4262; }}
  </style>
{android_redirect}
</head>
<body>
  <main>
    <h1>{escape(article.title)}</h1>
    <p>The UP Media app me article open ho raha hai. Agar app installed nahi hai to Play Store se install karein.</p>
    <a class="primary" href="{escape(app_url)}">Open in app</a>
    <a class="secondary" href="{escape(play_url)}">Install from Play Store</a>
    <a class="secondary" href="{escape(web_url)}">Read on web</a>
  </main>
</body>
</html>"""
    return HttpResponse(html)


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
