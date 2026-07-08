from django.contrib import admin

from .models import ShareCampaign, ShareDelivery, ShareTarget


@admin.register(ShareTarget)
class ShareTargetAdmin(admin.ModelAdmin):
    list_display = ("name", "target_type", "category", "is_active", "default_selected", "display_order")
    list_editable = ("is_active", "default_selected", "display_order")
    list_filter = ("target_type", "category", "is_active", "default_selected")
    search_fields = ("name", "category", "identifier", "group_url")


class ShareDeliveryInline(admin.TabularInline):
    model = ShareDelivery
    extra = 0
    readonly_fields = ("status", "manual_share_url", "response", "sent_at", "created_at")
    autocomplete_fields = ("target",)


@admin.register(ShareCampaign)
class ShareCampaignAdmin(admin.ModelAdmin):
    list_display = ("title", "article", "status", "delay_seconds", "created_by", "created_at", "completed_at")
    list_filter = ("status", "created_at")
    search_fields = ("title", "caption", "link", "article__title")
    autocomplete_fields = ("article", "created_by")
    inlines = (ShareDeliveryInline,)


@admin.register(ShareDelivery)
class ShareDeliveryAdmin(admin.ModelAdmin):
    list_display = ("campaign", "target", "status", "sent_at")
    list_filter = ("status", "target__target_type", "target__category")
    search_fields = ("campaign__title", "target__name", "response")
    autocomplete_fields = ("campaign", "target")
