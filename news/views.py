import json

from django.conf import settings
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from .models import Article, Category, City, State


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
    article = get_object_or_404(Article.published.select_related("category", "state", "city", "author"), slug=slug)
    related_articles = Article.published.filter(category=article.category).exclude(pk=article.pk).select_related("category", "state", "city")[:4]
    absolute_url = request.build_absolute_uri(article.get_absolute_url())
    image_url = ""
    if article.featured_image:
        image_url = request.build_absolute_uri(article.featured_image.url)
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
            "schema_json": json.dumps(schema),
        },
    )
