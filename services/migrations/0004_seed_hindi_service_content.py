from django.db import migrations


HINDI_SERVICES = {
    "django-website-development": {
        "name_hi": "Django वेबसाइट डेवलपमेंट",
        "short_description_hi": "Business, news portal aur service brand ke liye fast, secure aur SEO-ready Django website.",
        "description_hi": "हम admin panel, responsive frontend, SEO pages, forms, media upload और deployment support के साथ custom Django websites बनाते हैं.",
    },
    "news-portal-development": {
        "name_hi": "न्यूज़ पोर्टल डेवलपमेंट",
        "short_description_hi": "Categories, state-city pages, SEO URLs, sitemap, RSS aur social sharing ke saath complete news portal.",
        "description_hi": "हम article publishing, Google-friendly URLs, media handling, ads sections, RSS, sitemap और admin workflow के साथ full news website बनाते हैं.",
    },
    "seo-google-indexing-setup": {
        "name_hi": "SEO और Google Indexing Setup",
        "short_description_hi": "Ranking-ready pages ke liye meta tags, sitemap, schema, robots.txt aur Search Console setup.",
        "description_hi": "हम title/meta structure, canonical URLs, sitemap, robots.txt, schema markup और content guidance सहित technical SEO foundation setup करते हैं.",
    },
    "python-automation": {
        "name_hi": "Python Automation",
        "short_description_hi": "Reports, data entry, scraping aur daily business tasks automate karne ke liye Python tools.",
        "description_hi": "हम repetitive काम, Excel/report workflows, data processing, scraping, APIs और internal tools के लिए Python automation बनाते हैं.",
    },
    "gen-ai-web-apps": {
        "name_hi": "Gen AI Web Apps",
        "short_description_hi": "Modern business ke liye AI-powered web apps, chat tools, content helpers aur automation products.",
        "description_hi": "हम content workflows, chat assistants, lead tools और business automation के लिए Python और modern APIs पर practical AI web apps बनाते हैं.",
    },
    "api-backend-development": {
        "name_hi": "API और Backend Development",
        "short_description_hi": "Reliable backend systems, REST APIs, database design, authentication aur admin dashboards.",
        "description_hi": "हम Django के साथ scalable backend systems, database models, APIs, authentication, admin dashboards और deployment support बनाते हैं.",
    },
}


def fill_hindi_content(apps, schema_editor):
    Service = apps.get_model("services", "Service")
    for slug, data in HINDI_SERVICES.items():
        Service.objects.filter(slug=slug).update(**data)


def clear_hindi_content(apps, schema_editor):
    Service = apps.get_model("services", "Service")
    Service.objects.filter(slug__in=HINDI_SERVICES.keys()).update(
        name_hi="",
        short_description_hi="",
        description_hi="",
    )


class Migration(migrations.Migration):
    dependencies = [
        ("services", "0003_service_description_hi_service_name_hi_and_more"),
    ]

    operations = [
        migrations.RunPython(fill_hindi_content, clear_hindi_content),
    ]
