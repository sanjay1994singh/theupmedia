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
    return render(request, "blog/post_detail.html", {"post": post, "related_posts": related_posts})

# Create your views here.
