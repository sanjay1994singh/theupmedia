import hashlib
import json
from pathlib import Path
from urllib.parse import quote_plus

from django.conf import settings
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from PIL import Image, ImageOps

from .models import Article, ArticleRead, ArticleSlugRedirect, Category, City, State


BOT_KEYWORDS = (
    "bot",
    "crawl",
    "spider",
    "slurp",
    "facebookexternalhit",
    "whatsapp",
    "telegrambot",
    "twitterbot",
    "linkedinbot",
)


def public_absolute_url(path):
    return f"{settings.SITE_DOMAIN}{path}"


def client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def is_bot_request(request):
    user_agent = request.META.get("HTTP_USER_AGENT", "").lower()
    return any(keyword in user_agent for keyword in BOT_KEYWORDS)


def read_fingerprint(request):
    if request.user.is_authenticated:
        raw = f"user:{request.user.pk}"
    else:
        if not request.session.session_key:
            request.session.create()
        raw = "|".join(
            [
                "anon",
                request.session.session_key or "",
                client_ip(request),
                request.META.get("HTTP_USER_AGENT", ""),
            ]
        )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def user_agent_hash(request):
    return hashlib.sha256(request.META.get("HTTP_USER_AGENT", "").encode("utf-8")).hexdigest()


def share_image(request, slug):
    article = get_object_or_404(Article.published.select_related("category", "state", "city"), slug=slug)
    cache_dir = settings.MEDIA_ROOT / "share" / "articles"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{article.slug}-cover.jpg"

    if not cache_path.exists() or cache_path.stat().st_mtime < article.updated_at.timestamp():
        size = (1200, 630)
        if article.featured_image and Path(article.featured_image.path).exists():
            source = Image.open(article.featured_image.path).convert("RGB")
            image = ImageOps.fit(source, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        else:
            image = Image.new("RGB", size, "#b51f2a")

        image.save(cache_path, "JPEG", quality=90, optimize=True)
        with open(cache_path, "rb") as image_file:
            response = HttpResponse(image_file.read(), content_type="image/jpeg")
        response["Cache-Control"] = "public, max-age=86400"
        return response


    with open(cache_path, "rb") as image_file:
        response = HttpResponse(image_file.read(), content_type="image/jpeg")
    response["Cache-Control"] = "public, max-age=86400"
    return response


def article_list(request):
    articles = Article.published.select_related("category", "state", "city", "author")
    paginator = Paginator(articles, 12)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "news/article_list.html", {"page_obj": page_obj})


def category_detail(request, slug):
    category = get_object_or_404(Category, slug=slug, is_active=True)
    articles = Article.published.filter(category=category).select_related("category", "state", "city", "author")
    paginator = Paginator(articles, 12)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "news/category_detail.html", {"category": category, "page_obj": page_obj})


def state_detail(request, state_slug):
    state = get_object_or_404(State, slug=state_slug, is_active=True)
    articles = Article.published.filter(state=state).select_related("category", "state", "city", "author")
    paginator = Paginator(articles, 12)
    page_obj = paginator.get_page(request.GET.get("page"))
    cities = state.cities.filter(is_active=True)
    return render(request, "news/state_detail.html", {"state": state, "cities": cities, "page_obj": page_obj})


def city_detail(request, state_slug, city_slug):
    city = get_object_or_404(City, state__slug=state_slug, slug=city_slug, is_active=True, state__is_active=True)
    articles = Article.published.filter(city=city).select_related("category", "state", "city", "author")
    paginator = Paginator(articles, 12)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "news/city_detail.html", {"city": city, "state": city.state, "page_obj": page_obj})


def state_category_detail(request, state_slug, category_slug):
    state = get_object_or_404(State, slug=state_slug, is_active=True)
    category = get_object_or_404(Category, slug=category_slug, is_active=True)
    articles = Article.published.filter(state=state, category=category).select_related("category", "state", "city", "author")
    paginator = Paginator(articles, 12)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "news/state_category_detail.html", {"state": state, "category": category, "page_obj": page_obj})


def city_category_detail(request, state_slug, city_slug, category_slug):
    city = get_object_or_404(City, state__slug=state_slug, slug=city_slug, is_active=True, state__is_active=True)
    category = get_object_or_404(Category, slug=category_slug, is_active=True)
    articles = Article.published.filter(city=city, category=category).select_related("category", "state", "city", "author")
    paginator = Paginator(articles, 12)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "news/city_category_detail.html", {"city": city, "state": city.state, "category": category, "page_obj": page_obj})


def article_detail(request, slug):
    try:
        article = Article.published.select_related("category", "state", "city", "author").get(slug=slug)
    except Article.DoesNotExist:
        if slug.isdigit():
            article_by_id = get_object_or_404(Article.published.select_related("category", "state", "city", "author"), pk=int(slug))
            return redirect(article_by_id.get_absolute_url(), permanent=True)
        slug_redirect = get_object_or_404(ArticleSlugRedirect.objects.select_related("article"), old_slug=slug)
        return redirect(slug_redirect.article.get_absolute_url(), permanent=True)
    if not is_bot_request(request):
        ArticleRead.record(
            article=article,
            request=request,
            fingerprint=read_fingerprint(request),
            ip_address=client_ip(request),
            user_agent_hash=user_agent_hash(request),
        )
    related_articles = Article.published.filter(category=article.category).exclude(pk=article.pk).select_related("category", "state", "city")[:4]
    absolute_url = request.build_absolute_uri(article.get_absolute_url())
    share_image_url = public_absolute_url(reverse("news:share_image", kwargs={"slug": article.slug}))
    share_image_url = f"{share_image_url}?v={int(article.updated_at.timestamp())}"
    image_url = share_image_url
    schema = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": article.title,
        "description": article.meta_description,
        "datePublished": article.published_at.isoformat(),
        "dateModified": article.updated_at.isoformat(),
        "mainEntityOfPage": absolute_url,
        "publisher": {
            "@type": "Organization",
            "name": settings.SITE_NAME,
            "logo": {
                "@type": "ImageObject",
                "url": f"{settings.SITE_DOMAIN}/static/img/logo.png",
            },
        },
    }
    if image_url:
        schema["image"] = [image_url]
    if article.author:
        schema["author"] = {"@type": "Person", "name": str(article.author)}
    if article.city or article.state:
        schema["contentLocation"] = {
            "@type": "Place",
            "name": article.city.name if article.city else article.state.name,
        }
    return render(
        request,
        "news/article_detail.html",
        {
            "article": article,
            "related_articles": related_articles,
            "absolute_url": absolute_url,
            "share_url": public_absolute_url(article.get_absolute_url()),
            "share_image_url": share_image_url,
            "whatsapp_share_url": f"https://api.whatsapp.com/send?text={quote_plus(article.title + ' ' + public_absolute_url(article.get_absolute_url()))}",
            "facebook_share_url": f"https://www.facebook.com/sharer/sharer.php?u={quote_plus(public_absolute_url(article.get_absolute_url()))}",
            "twitter_share_url": f"https://twitter.com/intent/tweet?text={quote_plus(article.title)}&url={quote_plus(public_absolute_url(article.get_absolute_url()))}",
            "schema_json": json.dumps(schema),
        },
    )
