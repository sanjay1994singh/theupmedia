from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("contact/", views.contact, name="contact"),
    path("privacy-policy/", views.privacy_policy, name="privacy_policy"),
    path("terms-and-conditions/", views.terms, name="terms"),
    path("disclaimer/", views.disclaimer, name="disclaimer"),
    path("editorial-policy/", views.editorial_policy, name="editorial_policy"),
    path("fact-checking-policy/", views.fact_checking_policy, name="fact_checking_policy"),
    path("corrections-policy/", views.corrections_policy, name="corrections_policy"),
    path("robots.txt", views.robots_txt, name="robots_txt"),
    path("ads.txt", views.ads_txt, name="ads_txt"),
    path("sitemap.xml", views.sitemap_xml, name="sitemap"),
    path("news-sitemap.xml", views.news_sitemap_xml, name="news_sitemap"),
    path("rss.xml", views.rss_xml, name="rss"),
    path("health/", views.health, name="health"),
]
