from urllib.parse import quote

from django.db import models
from django.template.defaultfilters import slugify
from django.urls import reverse

WHATSAPP_NUMBER = "916397712918"


class Service(models.Model):
    name = models.CharField(max_length=160)
    name_hi = models.CharField("Hindi name", max_length=180, blank=True)
    slug = models.SlugField(max_length=180, unique=True, blank=True)
    short_description = models.TextField(help_text="Short service pitch for cards and snippets.")
    short_description_hi = models.TextField("Hindi short description", blank=True)
    description = models.TextField()
    description_hi = models.TextField("Hindi description", blank=True)
    image_path = models.CharField(max_length=220, blank=True, help_text="Static image path, example: img/services/seo/service.svg")
    icon_label = models.CharField(max_length=40, blank=True, help_text="Short visual label, example: SEO, AI, Web")
    starting_price = models.CharField(max_length=80, blank=True)
    delivery_time = models.CharField(max_length=80, blank=True)
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)
    meta_title = models.CharField(max_length=160, blank=True)
    meta_description = models.CharField(max_length=220, blank=True)
    meta_keywords = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "name"]
        indexes = [
            models.Index(fields=["is_active", "display_order"], name="service_active_order_idx"),
            models.Index(fields=["slug"], name="service_slug_idx"),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)[:150] or "service"
            slug = base_slug
            counter = 2
            while Service.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        if not self.meta_title:
            self.meta_title = self.name[:160]
        if not self.meta_description:
            self.meta_description = self.short_description[:220]
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("services:service_detail", kwargs={"slug": self.slug})

    @property
    def whatsapp_message(self):
        service_label = self.name
        if self.name_hi:
            service_label = f"{self.name_hi} / {self.name}"
        return (
            f"नमस्ते, मुझे {service_label} सेवा के बारे में जानकारी चाहिए। "
            f"कृपया पूरी डिटेल भेजें।\n"
            f"Hello, I want details about {self.name} service. Please share information."
        )

    @property
    def whatsapp_url(self):
        return f"https://wa.me/{WHATSAPP_NUMBER}?text={quote(self.whatsapp_message)}"

    def __str__(self):
        return self.name
