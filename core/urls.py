from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("robots.txt", views.robots_txt, name="robots_txt"),
    path("sitemap.xml", views.sitemap_xml, name="sitemap"),
    path("news-sitemap.xml", views.news_sitemap_xml, name="news_sitemap"),
    path("rss.xml", views.rss_xml, name="rss"),
    path("health/", views.health, name="health"),
]
