from django.contrib import admin

from .models import Service


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "name_hi", "is_active", "is_featured", "display_order", "starting_price", "delivery_time")
    list_editable = ("is_active", "is_featured", "display_order")
    list_filter = ("is_active", "is_featured")
    search_fields = ("name", "name_hi", "short_description", "short_description_hi", "description", "description_hi", "meta_keywords")
    prepopulated_fields = {"slug": ("name",)}
    fieldsets = (
        ("English Service", {"fields": ("name", "slug", "short_description", "description", "icon_label")}),
        ("Hindi Service", {"fields": ("name_hi", "short_description_hi", "description_hi")}),
        ("Business Details", {"fields": ("starting_price", "delivery_time", "is_featured", "is_active", "display_order")}),
        ("SEO", {"fields": ("meta_title", "meta_description", "meta_keywords")}),
    )
