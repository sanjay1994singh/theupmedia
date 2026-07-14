from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from services.models import Service


class SubscriptionPlan(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="subscription_plans")
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True, blank=True)
    duration_months = models.PositiveSmallIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="INR")
    description = models.TextField(blank=True)
    features = models.TextField(blank=True, help_text="One feature per line.")
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "price", "name"]
        indexes = [
            models.Index(fields=["is_active", "display_order"], name="sub_plan_active_order_idx"),
            models.Index(fields=["service", "is_active"], name="sub_plan_service_active_idx"),
        ]

    def save(self, *args, **kwargs):
        if not self.slug or SubscriptionPlan.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
            base = f"{self.service.slug}-{self.duration_months}-month-{self.name}".lower()
            from django.template.defaultfilters import slugify

            slug = slugify(base)[:160] or f"plan-{uuid4().hex[:8]}"
            counter = 2
            while SubscriptionPlan.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{slugify(base)[:150]}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def amount_paise(self):
        return int(self.price * Decimal("100"))

    def get_absolute_url(self):
        return reverse("services:service_detail", kwargs={"slug": self.service.slug})

    def __str__(self):
        return f"{self.service.name} - {self.name} ({self.duration_months} month)"


class WishlistItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscription_wishlist")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE, related_name="wishlist_items")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "plan")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} - {self.plan}"


class CartItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscription_cart")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE, related_name="cart_items")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "plan")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} - {self.plan}"


class ServiceOrder(models.Model):
    class Status(models.TextChoices):
        CREATED = "created", "Created"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="service_orders")
    receipt = models.CharField(max_length=80, unique=True, default="")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CREATED, db_index=True)
    currency = models.CharField(max_length=3, default="INR")
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    amount_paise = models.PositiveIntegerField(default=0)
    razorpay_order_id = models.CharField(max_length=120, blank=True, db_index=True)
    razorpay_payment_id = models.CharField(max_length=120, blank=True)
    razorpay_signature = models.CharField(max_length=255, blank=True)
    paid_at = models.DateTimeField(blank=True, null=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.receipt:
            self.receipt = f"svc-{uuid4().hex[:18]}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.receipt} - {self.user} - {self.status}"


class ServiceOrderItem(models.Model):
    order = models.ForeignKey(ServiceOrder, on_delete=models.CASCADE, related_name="items")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name="order_items")
    service_name = models.CharField(max_length=180)
    plan_name = models.CharField(max_length=180)
    duration_months = models.PositiveSmallIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    amount_paise = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.service_name} - {self.plan_name}"


class UserServiceSubscription(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="service_subscriptions")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name="user_subscriptions")
    order = models.ForeignKey(ServiceOrder, on_delete=models.SET_NULL, blank=True, null=True, related_name="subscriptions")
    starts_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-expires_at"]
        indexes = [
            models.Index(fields=["user", "is_active", "expires_at"], name="user_sub_active_exp_idx"),
        ]

    def __str__(self):
        return f"{self.user} - {self.plan} until {self.expires_at:%Y-%m-%d}"


class PaymentTransaction(models.Model):
    order = models.ForeignKey(ServiceOrder, on_delete=models.CASCADE, related_name="transactions")
    razorpay_order_id = models.CharField(max_length=120)
    razorpay_payment_id = models.CharField(max_length=120, blank=True)
    razorpay_signature = models.CharField(max_length=255, blank=True)
    is_signature_valid = models.BooleanField(default=False)
    raw_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.razorpay_payment_id or self.razorpay_order_id
