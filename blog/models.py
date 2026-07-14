from django.conf import settings
from django.db import models
from django.template.defaultfilters import slugify
from django.urls import reverse
from django.utils import timezone
from django_ckeditor_5.fields import CKEditor5Field


class PublishedPostManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(status=BlogPost.Status.PUBLISHED, published_at__lte=timezone.now())


class BlogPost(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    title = models.CharField(max_length=220)
    slug = models.SlugField(max_length=240, unique=True, blank=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="blog_posts")
    excerpt = models.TextField(help_text="Short intro for listing pages and Google snippets.")
    content = CKEditor5Field("Content", config_name="article")
    featured_image = models.ImageField(upload_to="blog/%Y/%m/", blank=True, null=True)
    image_alt_text = models.CharField(max_length=180, blank=True)
    focus_keyword = models.CharField(max_length=120, blank=True, help_text="Main SEO keyword for this blog.")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    is_featured = models.BooleanField(default=False)
    meta_title = models.CharField(max_length=160, blank=True)
    meta_description = models.CharField(max_length=220, blank=True)
    meta_keywords = models.CharField(max_length=255, blank=True)
    canonical_url = models.URLField(blank=True)
    published_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = models.Manager()
    published = PublishedPostManager()

    class Meta:
        ordering = ["-published_at"]
        indexes = [
            models.Index(fields=["status", "-published_at"], name="blog_post_status_pub_idx"),
            models.Index(fields=["slug"], name="blog_post_slug_idx"),
            models.Index(fields=["is_featured", "-published_at"], name="blog_post_featured_idx"),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)[:210] or f"blog-{timezone.now():%Y%m%d%H%M%S}"
            slug = base_slug
            counter = 2
            while BlogPost.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        if not self.meta_title:
            self.meta_title = self.title[:160]
        if not self.meta_description:
            self.meta_description = self.excerpt[:220]
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("blog:post_detail", kwargs={"slug": self.slug})

    def __str__(self):
        return self.title

# Create your models here.
