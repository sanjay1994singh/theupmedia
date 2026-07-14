import hmac
import json
from calendar import monthrange
from decimal import Decimal
from hashlib import sha256

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .models import CartItem, PaymentTransaction, ServiceOrder, ServiceOrderItem, SubscriptionPlan, UserServiceSubscription, WishlistItem


def add_months(value, months):
    month = value.month - 1 + months
    year = value.year + month // 12
    month = month % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def active_plan_queryset():
    return SubscriptionPlan.objects.select_related("service").filter(is_active=True, service__is_active=True)


def parse_json_or_post(request):
    if request.content_type and "application/json" in request.content_type:
        try:
            return json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return {}
    return request.POST


def razorpay_client():
    key_id = getattr(settings, "RAZORPAY_KEY_ID", "")
    key_secret = getattr(settings, "RAZORPAY_KEY_SECRET", "")
    if not key_id or not key_secret:
        raise RuntimeError("Razorpay credentials are not configured.")
    try:
        import razorpay
    except ImportError as exc:
        raise RuntimeError("Razorpay SDK is not installed. Run: pip install razorpay") from exc
    return razorpay.Client(auth=(key_id, key_secret))


@login_required
@require_POST
def add_to_cart(request, plan_id):
    plan = get_object_or_404(active_plan_queryset(), pk=plan_id)
    CartItem.objects.get_or_create(user=request.user, plan=plan)
    messages.success(request, "Service cart me add ho gayi.")
    return redirect("subscriptions:cart")


@login_required
@require_POST
def remove_from_cart(request, item_id):
    get_object_or_404(CartItem, pk=item_id, user=request.user).delete()
    messages.success(request, "Cart item remove ho gaya.")
    return redirect("subscriptions:cart")


@login_required
@require_POST
def toggle_wishlist(request, plan_id):
    plan = get_object_or_404(active_plan_queryset(), pk=plan_id)
    item, created = WishlistItem.objects.get_or_create(user=request.user, plan=plan)
    if created:
        messages.success(request, "Wishlist me add ho gaya.")
    else:
        item.delete()
        messages.success(request, "Wishlist se remove ho gaya.")
    return redirect(request.POST.get("next") or "subscriptions:wishlist")


@login_required
@require_GET
def cart(request):
    items = CartItem.objects.select_related("plan", "plan__service").filter(user=request.user)
    total = sum((item.plan.price for item in items), Decimal("0.00"))
    return render(
        request,
        "subscriptions/cart.html",
        {
            "items": items,
            "total": total,
            "total_paise": int(total * Decimal("100")),
            "razorpay_key_id": settings.RAZORPAY_KEY_ID,
        },
    )


@login_required
@require_GET
def wishlist(request):
    items = WishlistItem.objects.select_related("plan", "plan__service").filter(user=request.user)
    return render(request, "subscriptions/wishlist.html", {"items": items})


@login_required
@require_GET
def orders(request):
    order_list = ServiceOrder.objects.prefetch_related("items").filter(user=request.user)
    return render(request, "subscriptions/orders.html", {"orders": order_list})


@login_required
@require_GET
def my_subscriptions(request):
    subscriptions = UserServiceSubscription.objects.select_related("plan", "plan__service").filter(user=request.user)
    return render(request, "subscriptions/my_subscriptions.html", {"subscriptions": subscriptions})


def build_order_from_cart(user):
    cart_items = list(CartItem.objects.select_related("plan", "plan__service").filter(user=user, plan__is_active=True, plan__service__is_active=True))
    if not cart_items:
        return None, "Cart is empty."
    total = sum((item.plan.price for item in cart_items), Decimal("0.00"))
    amount_paise = int(total * Decimal("100"))
    if amount_paise < 100:
        return None, "Minimum payment amount is 100 paise."
    order = ServiceOrder.objects.create(user=user, amount=total, amount_paise=amount_paise, currency="INR")
    for item in cart_items:
        ServiceOrderItem.objects.create(
            order=order,
            plan=item.plan,
            service_name=item.plan.service.name[:180],
            plan_name=item.plan.name[:180],
            duration_months=item.plan.duration_months,
            price=item.plan.price,
            amount_paise=item.plan.amount_paise,
        )
    return order, ""


@login_required
@require_POST
def create_order(request):
    with transaction.atomic():
        order, error = build_order_from_cart(request.user)
        if error:
            return JsonResponse({"success": False, "error": error}, status=400)
        receipt = order.receipt

    try:
        client = razorpay_client()
        razorpay_order = client.order.create(
            {
                "amount": order.amount_paise,
                "currency": order.currency,
                "receipt": receipt,
                "payment_capture": 1,
            }
        )
    except Exception as exc:
        status_code = getattr(exc, "status_code", 500)
        error_message = str(exc) or "Razorpay order create failed."
        order.status = ServiceOrder.Status.FAILED
        order.error_message = error_message[:2000]
        order.save(update_fields=["status", "error_message", "updated_at"])
        if "Authentication failed" in error_message:
            error_message = "Razorpay authentication failed. Please update valid Test Mode key ID and secret in .env, then restart the server."
            status_code = 401
        return JsonResponse({"success": False, "error": error_message}, status=401 if status_code == 401 else 500)

    order.razorpay_order_id = razorpay_order["id"]
    order.save(update_fields=["razorpay_order_id", "updated_at"])
    return JsonResponse(
        {
            "success": True,
            "key_id": settings.RAZORPAY_KEY_ID,
            "order_id": order.razorpay_order_id,
            "amount": order.amount_paise,
            "currency": order.currency,
            "name": settings.SITE_NAME,
            "description": f"{settings.SITE_NAME} service subscription",
            "prefill": {
                "name": request.user.get_full_name() or request.user.username,
                "email": request.user.email,
                "contact": getattr(request.user, "phone_number", ""),
            },
        }
    )


@login_required
@require_POST
def verify_payment(request):
    data = parse_json_or_post(request)
    payment_id = (data.get("razorpay_payment_id") or "").strip()
    order_id = (data.get("razorpay_order_id") or "").strip()
    signature = (data.get("razorpay_signature") or "").strip()
    if not payment_id or not order_id or not signature:
        return JsonResponse({"success": False, "error": "Missing payment verification fields."}, status=400)

    order = get_object_or_404(ServiceOrder.objects.prefetch_related("items", "items__plan"), user=request.user, razorpay_order_id=order_id)
    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode("utf-8"),
        f"{order_id}|{payment_id}".encode("utf-8"),
        sha256,
    ).hexdigest()
    is_valid = hmac.compare_digest(expected, signature)
    PaymentTransaction.objects.create(
        order=order,
        razorpay_order_id=order_id,
        razorpay_payment_id=payment_id,
        razorpay_signature=signature,
        is_signature_valid=is_valid,
        raw_payload=dict(data),
    )
    if not is_valid:
        order.status = ServiceOrder.Status.FAILED
        order.error_message = "Razorpay signature mismatch."
        order.save(update_fields=["status", "error_message", "updated_at"])
        return JsonResponse({"success": False, "error": "Signature mismatch."}, status=400)

    with transaction.atomic():
        order.status = ServiceOrder.Status.PAID
        order.razorpay_payment_id = payment_id
        order.razorpay_signature = signature
        order.paid_at = timezone.now()
        order.error_message = ""
        order.save(update_fields=["status", "razorpay_payment_id", "razorpay_signature", "paid_at", "error_message", "updated_at"])
        now = timezone.now()
        for item in order.items.select_related("plan"):
            active = UserServiceSubscription.objects.filter(user=request.user, plan=item.plan, is_active=True, expires_at__gt=now).order_by("-expires_at").first()
            start = active.expires_at if active else now
            expires = add_months(start, item.duration_months)
            if active:
                active.expires_at = expires
                active.order = order
                active.save(update_fields=["expires_at", "order"])
            else:
                UserServiceSubscription.objects.create(user=request.user, plan=item.plan, order=order, starts_at=start, expires_at=expires)
        CartItem.objects.filter(user=request.user, plan__in=[item.plan for item in order.items.all()]).delete()

    return JsonResponse({"success": True, "redirect_url": reverse("subscriptions:my_subscriptions")})


@login_required
@require_POST
def payment_failed(request):
    data = parse_json_or_post(request)
    order_id = (data.get("razorpay_order_id") or "").strip()
    if order_id:
        ServiceOrder.objects.filter(user=request.user, razorpay_order_id=order_id).update(status=ServiceOrder.Status.FAILED, error_message=(data.get("error") or "Payment failed.")[:2000])
    return JsonResponse({"success": True})
