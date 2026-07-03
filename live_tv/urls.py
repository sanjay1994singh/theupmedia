from django.urls import path

from . import views

app_name = "live_tv"

urlpatterns = [
    path("api/live-tv/current/", views.current_live_tv_api, name="api_current"),
    path("api/videos/upload/", views.mobile_video_upload_api, name="api_video_upload"),
    path("api/live-tv/admin/login/", views.mobile_admin_login_api, name="api_admin_login"),
    path("api/live-tv/admin/logout/", views.mobile_admin_logout_api, name="api_admin_logout"),
    path("api/live-tv/admin/dashboard/", views.mobile_admin_dashboard_api, name="api_admin_dashboard"),
    path("api/live-tv/admin/channels/save/", views.mobile_admin_channel_save_api, name="api_admin_channel_save"),
    path("api/live-tv/admin/channels/<int:pk>/delete/", views.mobile_admin_channel_delete_api, name="api_admin_channel_delete"),
    path("live-tv/dashboard/", views.dashboard, name="dashboard"),
    path("live-tv/dashboard/<int:pk>/delete/", views.delete_channel, name="delete_channel"),
    path("live-tv/", views.live_tv_home, name="home"),
    path("live-tv/<slug:slug>/", views.live_tv_detail, name="detail"),
]
