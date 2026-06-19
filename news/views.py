import json
from pathlib import Path
from urllib.parse import quote_plus

from django.conf import settings
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.text import Truncator
from PIL import Image, ImageDraw, ImageFont, ImageOps

from .models import Article, ArticleSlugRedirect, Category, City, State


def public_absolute_url(path):
    return f"{settings.SITE_DOMAIN}{path}"


def _font(size):
    font_paths = [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for font_path in font_paths:
        if Path(font_path).exists():
            return ImageFont.truetype(font_path, size)
    return ImageFont.load_default()


def _wrap_text(text, font, max_width, draw):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        if draw.textbbox((0, 0), test, font=font)[2] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines[:4]


def share_image(request, slug):
    article = get_object_or_404(Article.published.select_related("category", "state", "city"), slug=slug)
    cache_dir = settings.MEDIA_ROOT / "share" / "articles"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{article.slug}.jpg"

    if not cache_path.exists() or cache_path.stat().st_mtime < article.updated_at.timestamp():
        size = (1200, 630)
        if article.featured_image and Path(article.featured_image.path).exists():
            image = Image.open(article.featured_image.path).convert("RGB")
            image = ImageOps.fit(image, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        else:
            image = Image.new("RGB", size, "#b51f2a")

        overlay = Image.new("RGBA", size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rectangle((0, 0, 1200, 630), fill=(0, 0, 0, 72))
        overlay_draw.rectangle((0, 360, 1200, 630), fill=(0, 0, 0, 188))
        image = Image.alpha_composite(image.convert("RGBA"), overlay)

        draw = ImageDraw.Draw(image)
        title_font = _font(58)
        meta_font = _font(28)
        brand_font = _font(32)
        category = article.category.name.upper()
        location = ""
        if article.city:
            location = f" • {article.city.name}"
        elif article.state:
            location = f" • {article.state.name}"
        draw.text((60, 42), settings.SITE_NAME, font=brand_font, fill="#ffffff")
        draw.text((60, 384), f"{category}{location}", font=meta_font, fill="#f5c451")
        title = Truncator(article.title).chars(105)
        y = 428
        for line in _wrap_text(title, title_font, 1080, draw):
            draw.text((60, y), line, font=title_font, fill="#ffffff")
            y += 66

        image.convert("RGB").save(cache_path, "JPEG", quality=88, optimize=True)

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
        slug_redirect = get_object_or_404(ArticleSlugRedirect.objects.select_related("article"), old_slug=slug)
        return redirect(slug_redirect.article.get_absolute_url(), permanent=True)
    related_articles = Article.published.filter(category=article.category).exclude(pk=article.pk).select_related("category", "state", "city")[:4]
    absolute_url = request.build_absolute_uri(article.get_absolute_url())
    share_image_url = public_absolute_url(reverse("news:share_image", kwargs={"slug": article.slug}))
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
