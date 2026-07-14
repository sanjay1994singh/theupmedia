from django.contrib import admin

from .models import CartItem, PaymentTransaction, ServiceOrder, ServiceOrderItem, SubscriptionPlan, UserServiceSubscription, WishlistItem


class ServiceOrderItemInline(admin.TabularInline):
    model = ServiceOrderItem
    extra = 0
    readonly_fields = ("plan", "service_name", "plan_name", "duration_months", "price", "amount_paise")
    can_delete = False


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ("service", "name", "duration_months", "price", "currency", "is_active", "display_order")
    list_filter = ("is_active", "currency", "duration_months")
    list_editable = ("is_active", "display_order")
    search_fields = ("service__name", "service__name_hi", "name", "description")


@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "created_at")
    search_fields = ("user__username", "plan__name", "plan__service__name")


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "created_at")
    search_fields = ("user__username", "plan__name", "plan__service__name")


@admin.register(ServiceOrder)
class ServiceOrderAdmin(admin.ModelAdmin):
    list_display = ("receipt", "user", "status", "amount", "currency", "razorpay_order_id", "paid_at", "created_at")
    list_filter = ("status", "currency")
    search_fields = ("receipt", "user__username", "user__email", "razorpay_order_id", "razorpay_payment_id")
    readonly_fields = ("receipt", "amount", "amount_paise", "razorpay_order_id", "razorpay_payment_id", "razorpay_signature", "paid_at", "created_at", "updated_at")
    inlines = [ServiceOrderItemInline]


@admin.register(UserServiceSubscription)
class UserServiceSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "starts_at", "expires_at", "is_active")
    list_filter = ("is_active",)
    search_fields = ("user__username", "user__email", "plan__name", "plan__service__name")


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ("order", "razorpay_order_id", "razorpay_payment_id", "is_signature_valid", "created_at")
    list_filter = ("is_signature_valid",)
    search_fields = ("order__receipt", "razorpay_order_id", "razorpay_payment_id")
    readonly_fields = ("order", "razorpay_order_id", "razorpay_payment_id", "razorpay_signature", "is_signature_valid", "raw_payload", "created_at")
