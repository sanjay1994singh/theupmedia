from django.urls import path

from . import views

app_name = "distribution"

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("campaigns/new/", views.campaign_create, name="campaign_create"),
    path("campaigns/<int:pk>/", views.campaign_detail, name="campaign_detail"),
    path("campaigns/<int:pk>/run/", views.campaign_run, name="campaign_run"),
    path("targets/", views.target_list, name="target_list"),
]
