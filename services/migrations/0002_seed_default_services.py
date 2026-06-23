from django.db import migrations


DEFAULT_SERVICES = [
    {
        "name": "Django Website Development",
        "slug": "django-website-development",
        "short_description": "Fast, secure, SEO-ready Django websites for businesses, news portals, and service brands.",
        "description": "We build custom Django websites with admin panels, responsive frontend, SEO pages, forms, media uploads, and deployment support.",
        "icon_label": "Web",
        "starting_price": "Custom quote",
        "delivery_time": "7-15 days",
        "display_order": 1,
        "is_featured": True,
        "meta_keywords": "Django website development, Python web developer, business website",
    },
    {
        "name": "News Portal Development",
        "slug": "news-portal-development",
        "short_description": "Complete news portal setup with categories, states, cities, SEO URLs, sitemap, RSS, and social sharing.",
        "description": "We create full news websites with article publishing, Google-friendly URLs, media handling, ads sections, RSS, sitemap, and admin workflow.",
        "icon_label": "News",
        "starting_price": "Custom quote",
        "delivery_time": "5-12 days",
        "display_order": 2,
        "is_featured": True,
        "meta_keywords": "news portal development, Hindi news website, SEO news website",
    },
    {
        "name": "SEO & Google Indexing Setup",
        "slug": "seo-google-indexing-setup",
        "short_description": "Technical SEO setup for ranking-ready pages, sitemaps, meta tags, schema, and search console basics.",
        "description": "We set up technical SEO foundations including title/meta structure, canonical URLs, sitemap, robots.txt, schema markup, and content guidance.",
        "icon_label": "SEO",
        "starting_price": "Custom quote",
        "delivery_time": "2-5 days",
        "display_order": 3,
        "is_featured": True,
        "meta_keywords": "SEO setup, Google indexing, technical SEO, sitemap setup",
    },
    {
        "name": "Python Automation",
        "slug": "python-automation",
        "short_description": "Python scripts and dashboards to automate reports, data entry, scraping, and daily business tasks.",
        "description": "We build Python automation for repetitive work, Excel/report workflows, data processing, scraping, APIs, and internal tools.",
        "icon_label": "Py",
        "starting_price": "Custom quote",
        "delivery_time": "3-10 days",
        "display_order": 4,
        "is_featured": True,
        "meta_keywords": "Python automation, business automation, Python scripts",
    },
    {
        "name": "Gen AI Web Apps",
        "slug": "gen-ai-web-apps",
        "short_description": "AI-powered web apps, chat tools, content helpers, and automation products for modern businesses.",
        "description": "We create practical AI web apps using Python and modern APIs for content workflows, chat assistants, lead tools, and business automation.",
        "icon_label": "AI",
        "starting_price": "Custom quote",
        "delivery_time": "7-20 days",
        "display_order": 5,
        "is_featured": True,
        "meta_keywords": "Gen AI web app, AI automation, Python AI developer",
    },
    {
        "name": "API & Backend Development",
        "slug": "api-backend-development",
        "short_description": "Reliable backend systems, REST APIs, database design, authentication, and admin dashboards.",
        "description": "We build scalable backend systems with Django, database models, APIs, authentication, admin dashboards, and deployment support.",
        "icon_label": "API",
        "starting_price": "Custom quote",
        "delivery_time": "5-15 days",
        "display_order": 6,
        "is_featured": True,
        "meta_keywords": "backend development, API development, Django REST API",
    },
]


def create_services(apps, schema_editor):
    Service = apps.get_model("services", "Service")
    for data in DEFAULT_SERVICES:
        Service.objects.update_or_create(slug=data["slug"], defaults=data)


def remove_services(apps, schema_editor):
    Service = apps.get_model("services", "Service")
    Service.objects.filter(slug__in=[service["slug"] for service in DEFAULT_SERVICES]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("services", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_services, remove_services),
    ]
