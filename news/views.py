import json

from django.conf import settings
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from .models import Article, Category


def article_list(request):
    articles = Article.published.select_related("category", "author")
    paginator = Paginator(articles, 12)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "news/article_list.html", {"page_obj": page_obj})


def category_detail(request, slug):
    category = get_object_or_404(Category, slug=slug, is_active=True)
    articles = Article.published.filter(category=category).select_related("category", "author")
    paginator = Paginator(articles, 12)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "news/category_detail.html", {"category": category, "page_obj": page_obj})


def article_detail(request, slug):
    article = get_object_or_404(Article.published.select_related("category", "author"), slug=slug)
    related_articles = Article.published.filter(category=article.category).exclude(pk=article.pk)[:4]
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
