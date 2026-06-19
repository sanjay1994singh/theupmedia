# The Up Media

SEO-focused Django news project with:

- Custom `accounts.User` model based on `AbstractUser`
- Google and Facebook social auth wiring through `social-auth-app-django`
- Admin-ready categories and articles
- Article SEO fields, canonical URLs, Open Graph tags, Twitter card tags, and NewsArticle JSON-LD
- `robots.txt`, `sitemap.xml`, `news-sitemap.xml`, and `rss.xml`
- Responsive homepage, category pages, article list, article detail, login, signup, and profile pages

## Run Locally

```powershell
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Open `http://127.0.0.1:8000/`.

## Admin Setup

```powershell
.\.venv\Scripts\python.exe manage.py createsuperuser
```

Then open `http://127.0.0.1:8000/admin/`.

## Production SEO Notes

Set these in `.env` before launch:

- `DEBUG=False`
- `SECRET_KEY` to a strong private value
- `ALLOWED_HOSTS` to your domain
- `CSRF_TRUSTED_ORIGINS` to your HTTPS domain
- `SITE_DOMAIN` to your public HTTPS URL
- Social auth client IDs and secrets

Google ranking cannot be guaranteed immediately by code, but this project includes the technical SEO foundation needed for crawlable, indexable news publishing.
