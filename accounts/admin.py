from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Profile", {"fields": ("avatar", "cover_image", "bio", "date_of_birth", "gender", "role", "designation", "organization")}),
        ("Contact", {"fields": ("phone_number", "alternate_phone", "website", "email_verified", "phone_verified")}),
        ("Address", {"fields": ("address_line_1", "address_line_2", "city", "state", "country", "postal_code")}),
        ("Preferences", {"fields": ("language", "timezone", "newsletter_subscribed")}),
        ("Social Links", {"fields": ("facebook", "twitter", "instagram", "linkedin", "youtube")}),
        ("Editorial Access", {"fields": ("is_author", "is_editor", "is_reporter", "is_verified")}),
        ("Profile Dates", {"fields": ("last_profile_update", "updated_at")}),
    )
    readonly_fields = ("updated_at",)
    list_display = ("username", "email", "first_name", "last_name", "role", "is_author", "is_editor", "is_staff")
    list_filter = ("role", "is_author", "is_editor", "is_reporter", "is_verified", "is_staff", "is_superuser", "is_active")
    search_fields = ("username", "email", "first_name", "last_name", "phone_number", "city", "organization")
