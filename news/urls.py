from django.urls import path

from . import views

app_name = "news"

urlpatterns = [
    path("news/", views.article_list, name="article_list"),
    path("category/<slug:slug>/", views.category_detail, name="category_detail"),
    path("state/<slug:state_slug>/", views.state_detail, name="state_detail"),
    path("state/<slug:state_slug>/category/<slug:category_slug>/", views.state_category_detail, name="state_category_detail"),
    path("state/<slug:state_slug>/<slug:city_slug>/", views.city_detail, name="city_detail"),
    path("state/<slug:state_slug>/<slug:city_slug>/category/<slug:category_slug>/", views.city_category_detail, name="city_category_detail"),
    path("news/<slug:slug>/", views.article_detail, name="article_detail"),
]
