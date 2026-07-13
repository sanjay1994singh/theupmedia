from django.urls import path

from . import views

app_name = "social_downloader"

urlpatterns = [
    path("", views.downloader_home, name="home"),
    path("history/", views.download_history, name="history"),
    path("status/<int:pk>/", views.download_status, name="status"),
    path("file/<int:pk>/", views.download_file, name="file"),
    path("delete/<int:pk>/", views.delete_download, name="delete"),
]
