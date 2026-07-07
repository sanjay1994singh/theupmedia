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
    path("api/live-tv/admin/settings/save/", views.mobile_admin_settings_save_api, name="api_admin_settings_save"),
    path("api/live-tv/admin/facebook-live/save/", views.mobile_admin_facebook_live_save_api, name="api_admin_facebook_live_save"),
    path("api/live-tv/admin/facebook-live/start/", views.mobile_admin_facebook_live_start_api, name="api_admin_facebook_live_start"),
    path("api/live-tv/admin/facebook-live/stop/", views.mobile_admin_facebook_live_stop_api, name="api_admin_facebook_live_stop"),
    path("api/live-tv/admin/facebook-live/status/", views.mobile_admin_facebook_live_status_api, name="api_admin_facebook_live_status"),
    path("api/live-tv/admin/channels/<int:pk>/delete/", views.mobile_admin_channel_delete_api, name="api_admin_channel_delete"),
    path("api/live-tv/admin/uploads/<int:pk>/update/", views.mobile_admin_upload_update_api, name="api_admin_upload_update"),
    path("api/live-tv/admin/uploads/<int:pk>/delete/", views.mobile_admin_upload_delete_api, name="api_admin_upload_delete"),
    path("api/live-tv/admin/render-social-video/", views.mobile_admin_render_social_video_api, name="api_admin_render_social_video"),
    path("api/live-tv/admin/render-social-video/<int:pk>/status/", views.mobile_admin_render_social_video_status_api, name="api_admin_render_social_video_status"),
    path("api/live-tv/admin/rendered-videos/<int:pk>/update/", views.mobile_admin_rendered_video_update_api, name="api_admin_rendered_video_update"),
    path("api/live-tv/admin/rendered-videos/<int:pk>/delete/", views.mobile_admin_rendered_video_delete_api, name="api_admin_rendered_video_delete"),
    path("api/live-tv/admin/media-downloads/start/", views.mobile_admin_media_download_start_api, name="api_admin_media_download_start"),
    path("api/live-tv/admin/media-downloads/<int:pk>/status/", views.mobile_admin_media_download_status_api, name="api_admin_media_download_status"),
    path("api/live-tv/admin/media-downloads/<int:pk>/update/", views.mobile_admin_media_download_update_api, name="api_admin_media_download_update"),
    path("api/live-tv/admin/media-downloads/<int:pk>/delete/", views.mobile_admin_media_download_delete_api, name="api_admin_media_download_delete"),
    path("downloads/", views.media_download_page, name="media_downloads"),
    path("downloads/<int:pk>/delete/", views.delete_media_download, name="delete_media_download"),
    path("live-tv/dashboard/", views.dashboard, name="dashboard"),
    path("live-tv/dashboard/<int:pk>/delete/", views.delete_channel, name="delete_channel"),
    path("live-tv/", views.live_tv_home, name="home"),
    path("live-tv/<slug:slug>/", views.live_tv_detail, name="detail"),
]

