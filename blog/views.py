from urllib.parse import quote_plus

from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from .models import BlogPost


def post_list(request):
    posts = BlogPost.published.select_related("author")
    paginator = Paginator(posts, 9)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "blog/post_list.html", {"page_obj": page_obj})


def post_detail(request, slug):
    post = get_object_or_404(BlogPost.published.select_related("author"), slug=slug)
    related_posts = BlogPost.published.exclude(pk=post.pk)[:3]
    share_url = request.build_absolute_uri(post.get_absolute_url())
    return render(
        request,
        "blog/post_detail.html",
        {
            "post": post,
            "related_posts": related_posts,
            "share_url": share_url,
            "whatsapp_share_url": f"https://api.whatsapp.com/send?text={quote_plus(post.title + ' ' + share_url)}",
            "facebook_share_url": f"https://www.facebook.com/sharer/sharer.php?u={quote_plus(share_url)}",
            "twitter_share_url": f"https://twitter.com/intent/tweet?text={quote_plus(post.title)}&url={quote_plus(share_url)}",
        },
    )

# Create your views here.
