from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "The Up Media Admin"
admin.site.site_title = "The Up Media"
admin.site.index_title = "The Up Media Dashboard"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("auth/", include("social_django.urls", namespace="social")),
    path("ckeditor5/", include("django_ckeditor_5.urls")),
    path("blog/", include("blog.urls")),
    path("services/", include("services.urls")),
    path("", include("core.urls")),
    path("", include("news.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
