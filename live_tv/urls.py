from django.urls import path

from . import views

app_name = "live_tv"

urlpatterns = [
    path("live-tv/dashboard/", views.dashboard, name="dashboard"),
    path("live-tv/dashboard/<int:pk>/delete/", views.delete_channel, name="delete_channel"),
    path("live-tv/", views.live_tv_home, name="home"),
    path("live-tv/<slug:slug>/", views.live_tv_detail, name="detail"),
]
