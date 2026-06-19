from django.conf import settings
from django.db import models
from django.db.models import F
from django.template.defaultfilters import slugify
from django.urls import reverse
from django.utils import timezone
from django_ckeditor_5.fields import CKEditor5Field

from .slug_utils import unique_article_slug


class PublishedManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(status=Article.Status.PUBLISHED, published_at__lte=timezone.now())


class Category(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    description = models.TextField(blank=True)
    meta_title = models.CharField(max_length=160, blank=True)
    meta_description = models.CharField(max_length=220, blank=True)
    image = models.ImageField(upload_to="categories/", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("news:category_detail", kwargs={"slug": self.slug})

    def __str__(self):
        return self.name


class State(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    description = models.TextField(blank=True)
    meta_title = models.CharField(max_length=160, blank=True)
    meta_description = models.CharField(max_length=220, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("news:state_detail", kwargs={"state_slug": self.slug})

    def __str__(self):
        return self.name


class City(models.Model):
    state = models.ForeignKey(State, on_delete=models.PROTECT, related_name="cities")
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, blank=True)
    description = models.TextField(blank=True)
    meta_title = models.CharField(max_length=160, blank=True)
    meta_description = models.CharField(max_length=220, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["state__name", "name"]
        verbose_name_plural = "Cities"
        constraints = [
            models.UniqueConstraint(fields=["state", "slug"], name="unique_city_slug_per_state"),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("news:city_detail", kwargs={"state_slug": self.state.slug, "city_slug": self.slug})

    def __str__(self):
        return f"{self.name}, {self.state.name}"


class Article(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    title = models.CharField(max_length=220)
    slug = models.SlugField(
        max_length=240,
        unique=True,
        blank=True,
        help_text="Leave blank to generate an SEO-friendly Hinglish URL from the Hindi title.",
    )
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="articles")
    state = models.ForeignKey(State, on_delete=models.PROTECT, related_name="articles", blank=True, null=True)
    city = models.ForeignKey(City, on_delete=models.PROTECT, related_name="articles", blank=True, null=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="articles", null=True, blank=True)
    summary = models.TextField(help_text="Short summary used on listing pages and search snippets.")
    content = CKEditor5Field("Content", config_name="article")
    featured_image = models.ImageField(upload_to="articles/%Y/%m/", blank=True, null=True)
    image_alt_text = models.CharField(max_length=180, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    is_featured = models.BooleanField(default=False)
    source_name = models.CharField(max_length=120, blank=True)
    source_url = models.URLField(blank=True)
    meta_title = models.CharField(max_length=160, blank=True)
    meta_description = models.CharField(max_length=220, blank=True)
    meta_keywords = models.CharField(max_length=255, blank=True)
    canonical_url = models.URLField(blank=True)
    unique_reads = models.PositiveIntegerField(default=0, editable=False)
    published_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = models.Manager()
    published = PublishedManager()

    class Meta:
        ordering = ["-published_at"]
        indexes = [
            models.Index(fields=["status", "-published_at"], name="news_articl_status_3401af_idx"),
            models.Index(fields=["slug"], name="news_articl_slug_359fc3_idx"),
            models.Index(fields=["is_featured", "-published_at"], name="news_articl_is_feat_c36d07_idx"),
            models.Index(fields=["state", "-published_at"], name="news_articl_state_6c1d8b_idx"),
            models.Index(fields=["city", "-published_at"], name="news_articl_city_9a4e22_idx"),
            models.Index(fields=["category", "state", "-published_at"], name="news_articl_cat_state_17a5_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.city and not self.state:
            self.state = self.city.state
        if not self.slug:
            self.slug = unique_article_slug(Article, self.title, self.pk)
        if not self.meta_title:
            self.meta_title = self.title[:160]
        if not self.meta_description:
            self.meta_description = self.summary[:220]
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("news:article_detail", kwargs={"slug": self.slug})

    def __str__(self):
        return self.title


class ArticleSlugRedirect(models.Model):
    old_slug = models.SlugField(max_length=240, unique=True)
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="slug_redirects")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.old_slug} -> {self.article.slug}"


class ArticleRead(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="reads")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="article_reads")
    fingerprint = models.CharField(max_length=64)
    session_key = models.CharField(max_length=40, blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent_hash = models.CharField(max_length=64, blank=True)
    first_read_at = models.DateTimeField(auto_now_add=True)
    last_read_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-first_read_at"]
        constraints = [
            models.UniqueConstraint(fields=["article", "fingerprint"], name="unique_article_read_fingerprint"),
        ]
        indexes = [
            models.Index(fields=["article", "-first_read_at"], name="news_read_article_first_idx"),
        ]

    def __str__(self):
        return f"{self.article_id} {self.fingerprint}"

    @classmethod
    def record(cls, article, request, fingerprint, ip_address="", user_agent_hash=""):
        user = request.user if request.user.is_authenticated else None
        session_key = request.session.session_key or ""
        read, created = cls.objects.get_or_create(
            article=article,
            fingerprint=fingerprint,
            defaults={
                "user": user,
                "session_key": session_key,
                "ip_address": ip_address or None,
                "user_agent_hash": user_agent_hash,
            },
        )
        if created:
            Article.objects.filter(pk=article.pk).update(unique_reads=F("unique_reads") + 1)
            article.unique_reads = (article.unique_reads or 0) + 1
        return read, created
