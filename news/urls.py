from django.urls import path

from . import views

app_name = "news"

urlpatterns = [
    path("news/", views.article_list, name="article_list"),
    path("category/<slug:slug>/", views.category_detail, name="category_detail"),
    path("news/<slug:slug>/", views.article_detail, name="article_detail"),
]
