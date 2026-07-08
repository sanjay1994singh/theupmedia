from urllib.parse import quote

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from news.models import Article


class ShareTarget(models.Model):
    class TargetType(models.TextChoices):
        WHATSAPP_GROUP = "whatsapp_group", "WhatsApp Group Manual Link"
        WHATSAPP_CONTACT = "whatsapp_contact", "WhatsApp Business Contact"
        TELEGRAM = "telegram", "Telegram Channel"
        FACEBOOK = "facebook", "Facebook Page"

    name = models.CharField(max_length=160)
    target_type = models.CharField(max_length=30, choices=TargetType.choices)
    category = models.CharField(max_length=80, blank=True, help_text="Mathura, UP, Crime, Politics etc.")
    identifier = models.CharField(max_length=220, blank=True, help_text="Phone number, Telegram chat id, Facebook page id, or internal note.")
    group_url = models.URLField(blank=True, help_text="Optional WhatsApp group invite/link for manual sharing.")
    is_active = models.BooleanField(default=True)
    default_selected = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["display_order", "name"]
        indexes = [
            models.Index(fields=["target_type", "is_active"], name="dist_target_type_active_idx"),
            models.Index(fields=["category", "is_active"], name="dist_target_cat_active_idx"),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_target_type_display()})"


class ShareCampaign(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="share_campaigns")
    title = models.CharField(max_length=220)
    caption = models.TextField()
    link = models.URLField()
    image_url = models.URLField(blank=True)
    targets = models.ManyToManyField(ShareTarget, through="ShareDelivery", related_name="campaigns")
    delay_seconds = models.PositiveIntegerField(default=15)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def share_text(self):
        return f"{self.caption}\n{self.link}".strip()

    def get_absolute_url(self):
        return reverse("distribution:campaign_detail", kwargs={"pk": self.pk})


class ShareDelivery(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        MANUAL = "manual", "Manual Share Required"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    campaign = models.ForeignKey(ShareCampaign, on_delete=models.CASCADE, related_name="deliveries")
    target = models.ForeignKey(ShareTarget, on_delete=models.CASCADE, related_name="deliveries")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    manual_share_url = models.URLField(blank=True)
    response = models.TextField(blank=True)
    sent_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["target__display_order", "target__name"]
        constraints = [
            models.UniqueConstraint(fields=["campaign", "target"], name="unique_distribution_delivery"),
        ]

    def mark_manual(self):
        self.status = self.Status.MANUAL
        self.manual_share_url = f"https://wa.me/?text={quote(self.campaign.share_text)}"
        self.response = "WhatsApp groups require manual sharing. Open the link and choose the group."
        self.sent_at = timezone.now()
        self.save(update_fields=["status", "manual_share_url", "response", "sent_at"])

    def __str__(self):
        return f"{self.campaign_id} -> {self.target.name}"
