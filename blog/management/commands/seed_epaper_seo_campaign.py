from datetime import datetime, time, timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from blog.models import BlogPost
from services.models import Service


SERVICE_SLUG = "epaper-website-app-development"
SERVICE_IMAGE = "img/services/seo/epaper-website-app-development.svg"
BLOG_IMAGE_DIR = "blog/epaper-seo"
WHATSAPP_NUMBER = "6397712918"
PHONE_NUMBER = "8279408396"

AUDIENCES = [
    ("local-newspaper", "Local Newspaper"),
    ("hindi-newspaper", "Hindi Newspaper"),
    ("district-media", "District Media"),
    ("weekly-newspaper", "Weekly Newspaper"),
    ("daily-newspaper", "Daily Newspaper"),
    ("print-media", "Print Media"),
    ("school-magazine", "School Magazine"),
    ("college-magazine", "College Magazine"),
    ("religious-magazine", "Religious Magazine"),
    ("community-newspaper", "Community Newspaper"),
    ("political-newspaper", "Political Newspaper"),
    ("business-magazine", "Business Magazine"),
    ("real-estate-magazine", "Real Estate Magazine"),
    ("classified-paper", "Classified Paper"),
    ("regional-news-brand", "Regional News Brand"),
    ("press-reporter-team", "Press Reporter Team"),
    ("youtube-news-channel", "YouTube News Channel"),
    ("city-news-portal", "City News Portal"),
    ("state-news-portal", "State News Portal"),
    ("media-startup", "Media Startup"),
    ("ngo-publication", "NGO Publication"),
    ("temple-publication", "Temple Publication"),
    ("event-magazine", "Event Magazine"),
    ("government-newsletter", "Government Newsletter"),
    ("business-directory", "Business Directory"),
]

TOPICS = [
    ("development-guide", "Development Guide"),
    ("cost-in-india", "Cost in India"),
    ("seo-strategy", "SEO Strategy"),
    ("google-indexing", "Google Indexing"),
    ("mobile-app", "Mobile App"),
    ("pdf-upload-system", "PDF Upload System"),
    ("admin-panel", "Admin Panel"),
    ("subscription-model", "Subscription Model"),
    ("ads-management", "Ads Management"),
    ("archive-system", "Archive System"),
    ("edition-management", "Edition Management"),
    ("page-flip-viewer", "Page Flip Viewer"),
    ("fast-loading", "Fast Loading"),
    ("whatsapp-sharing", "WhatsApp Sharing"),
    ("reader-experience", "Reader Experience"),
    ("publisher-workflow", "Publisher Workflow"),
    ("digital-growth", "Digital Growth"),
    ("lead-generation", "Lead Generation"),
    ("launch-checklist", "Launch Checklist"),
    ("professional-features", "Professional Features"),
]

PALETTES = [
    ("#991b1b", "#fff7ed", "#111827"),
    ("#0f766e", "#ecfeff", "#111827"),
    ("#1d4ed8", "#eff6ff", "#111827"),
    ("#7c2d12", "#fef3c7", "#111827"),
    ("#4c1d95", "#faf5ff", "#111827"),
    ("#166534", "#f0fdf4", "#111827"),
]


class Command(BaseCommand):
    help = "Seed e-paper service plus 500 SEO blogs scheduled two per day at 8 AM and 4 PM."

    def add_arguments(self, parser):
        parser.add_argument("--start-date", help="Schedule start date in YYYY-MM-DD format. Default: tomorrow.")
        parser.add_argument("--reschedule", action="store_true", help="Reset published_at for existing seeded posts.")
        parser.add_argument("--no-images", action="store_true", help="Only seed records, do not write SVG image files.")

    def handle(self, *args, **options):
        start_date = self._start_date(options.get("start_date"))
        media_dir = Path(settings.MEDIA_ROOT) / BLOG_IMAGE_DIR
        service_image_dir = Path(settings.BASE_DIR) / "static" / "img" / "services" / "seo"

        if not options["no_images"]:
            media_dir.mkdir(parents=True, exist_ok=True)
            service_image_dir.mkdir(parents=True, exist_ok=True)
            self._write_service_svg(service_image_dir / "epaper-website-app-development.svg")

        self._seed_service()

        created = 0
        updated = 0
        for index, (audience_slug, audience, topic_slug, topic) in enumerate(self._blog_rows(), start=1):
            slug = f"epaper-{audience_slug}-{topic_slug}"
            title = f"E-Paper Website and App for {audience}: {topic}"
            keyword = f"E-Paper {audience}"
            image_name = f"{slug}.svg"
            if not options["no_images"]:
                self._write_blog_svg(media_dir / image_name, title, keyword, index)

            scheduled_at = self._scheduled_at(start_date, index)
            defaults = {
                "title": title,
                "excerpt": self._excerpt(audience, topic),
                "content": self._content(audience, topic, keyword),
                "featured_image": f"{BLOG_IMAGE_DIR}/{image_name}",
                "image_alt_text": f"{title} - The Up Media",
                "focus_keyword": keyword,
                "status": BlogPost.Status.PUBLISHED,
                "is_featured": index <= 6,
                "meta_title": f"{title} | The Up Media",
                "meta_description": self._excerpt(audience, topic)[:220],
                "meta_keywords": (
                    f"{keyword}, e-paper website, epaper app, digital newspaper app, newspaper website development, "
                    "The Up Media"
                ),
                "canonical_url": "",
            }
            post = BlogPost.objects.filter(slug=slug).first()
            if post:
                for field, value in defaults.items():
                    setattr(post, field, value)
                if options["reschedule"]:
                    post.published_at = scheduled_at
                post.save()
                updated += 1
            else:
                BlogPost.objects.create(slug=slug, published_at=scheduled_at, **defaults)
                created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"E-paper SEO campaign ready. Service: {SERVICE_SLUG}. Blogs created: {created}, updated: {updated}. "
                f"Schedule starts: {start_date.isoformat()} 08:00, two posts per day."
            )
        )

    def _start_date(self, value):
        if not value:
            return timezone.localdate() + timedelta(days=1)
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError as exc:
            raise CommandError("--start-date must be in YYYY-MM-DD format.") from exc

    def _blog_rows(self):
        for audience_slug, audience in AUDIENCES:
            for topic_slug, topic in TOPICS:
                yield audience_slug, audience, topic_slug, topic

    def _scheduled_at(self, start_date, index):
        day_offset = (index - 1) // 2
        slot = time(8, 0) if index % 2 else time(16, 0)
        naive = datetime.combine(start_date + timedelta(days=day_offset), slot)
        return timezone.make_aware(naive, timezone.get_current_timezone())

    def _seed_service(self):
        description_hi = f"""## E-Paper Website aur Mobile App Development

The Up Media newspaper publishers, local media teams, magazine owners aur news brands ke liye complete e-paper website/app solution banata hai. Isme PDF edition upload, page-flip viewer, archive, category, subscription, WhatsApp sharing aur SEO-ready public pages include kiye ja sakte hain.

### E-Paper website/app kyun zaroori hai?

Print newspaper sirf local circulation tak limited reh sakta hai, lekin e-paper se aapka edition mobile readers, Google Search, social media aur WhatsApp audience tak pahunch sakta hai. Readers old editions search kar sakte hain, PDF download kar sakte hain aur advertisers ko digital visibility milti hai.

### Main features

* Daily/weekly edition upload
* PDF e-paper viewer aur mobile responsive page
* Edition archive by date, city, state and category
* SEO friendly URL, sitemap and meta tags
* WhatsApp share button and direct enquiry flow
* Advertisement slots and sponsored banners
* Subscription/payment gateway option
* Admin panel for publisher team
* Android app/web app integration

### English Summary

We build SEO-ready e-paper websites and mobile apps for newspapers, magazines and local media publishers. The system can include PDF uploads, archive search, page viewer, subscription plans, ads management, WhatsApp sharing and fast mobile pages.

### Important note

Google ranking, instant indexing, Google News approval or viral traffic is not guaranteed. We provide SEO-ready technical structure, useful content layout and best practices. Final results depend on content quality, competition, domain authority, user engagement and search engine policies.

### Contact

Phone: {PHONE_NUMBER}
WhatsApp: {WHATSAPP_NUMBER}
"""
        description_en = f"""## E-Paper Website and App Development

The Up Media builds e-paper websites and mobile apps for newspapers, magazines, local publishers and media brands. The platform can support PDF edition upload, archive pages, SEO-friendly URLs, reader sharing, ads sections and subscription options.

### What you can sell with this platform

* Digital newspaper subscriptions
* Paid e-paper access
* Banner advertisements
* Sponsored editions
* City-wise or category-wise campaigns
* Business listing and classifieds

### Contact

Phone: {PHONE_NUMBER}
WhatsApp: {WHATSAPP_NUMBER}
"""
        Service.objects.update_or_create(
            slug=SERVICE_SLUG,
            defaults={
                "name": "E-Paper Website and App Development",
                "name_hi": "ई-पेपर वेबसाइट और मोबाइल ऐप डेवलपमेंट",
                "short_description": "SEO-ready e-paper website and mobile app for newspapers, magazines and local media publishers.",
                "short_description_hi": "न्यूज़पेपर और मैगज़ीन publishers के लिए SEO-ready e-paper website/app solution.",
                "description": description_en,
                "description_hi": description_hi,
                "image_path": SERVICE_IMAGE,
                "icon_label": "EPAPER",
                "starting_price": "Custom quote",
                "delivery_time": "Depends on features",
                "is_featured": True,
                "is_active": True,
                "display_order": 18,
                "meta_title": "E-Paper Website and App Development | Newspaper Epaper Solution",
                "meta_description": "Get SEO-ready e-paper website and mobile app with PDF upload, archive, page viewer, subscription, ads and WhatsApp sharing.",
                "meta_keywords": "e-paper website development, epaper app development, newspaper app, digital newspaper solution",
            },
        )

    def _excerpt(self, audience, topic):
        return (
            f"{topic} guide for {audience} publishers planning an SEO-ready e-paper website, mobile app, "
            "PDF edition workflow and digital newspaper growth system."
        )

    def _content(self, audience, topic, keyword):
        return f"""
<h2>{keyword}: {topic}</h2>
<p>Digital publishing ka market fast grow kar raha hai. {audience} publishers ke liye e-paper website aur mobile app ek practical solution hai jisse print edition ko online audience tak pahunchaya ja sakta hai. Is guide me hum {topic.lower()} ke practical points cover kar rahe hain.</p>

<h3>E-Paper Platform ka business value</h3>
<p>Traditional newspaper circulation local area tak limited ho sakta hai. E-paper website readers ko mobile par edition padhne, old archive search karne, link share karne aur PDF access karne ka option deti hai. Isse publisher ko brand visibility, reader retention aur advertisement opportunities milti hain.</p>

<h3>Required Features</h3>
<ul>
  <li>PDF edition upload with date-wise archive</li>
  <li>SEO-friendly public URL for each edition</li>
  <li>Mobile responsive e-paper viewer</li>
  <li>City, state and category based organization</li>
  <li>WhatsApp sharing button for readers</li>
  <li>Advertisement slots for sponsors</li>
  <li>Subscription/payment option where required</li>
  <li>Admin panel for publisher team</li>
</ul>

<h3>SEO Strategy</h3>
<p>Har edition ka title, meta description, publication date, image preview aur internal links clear hone chahiye. Google ranking guaranteed nahi hoti, lekin clean structure, sitemap, fast loading pages aur useful content search discovery improve karte hain.</p>

<h3>Mobile App Advantage</h3>
<p>Mobile app se readers ko direct access, push notification, saved editions aur fast browsing experience mil sakta hai. Hindi aur regional audiences ke liye simple navigation, clear fonts aur low-data friendly pages important hote hain.</p>

<h3>Monetization Options</h3>
<p>E-paper platform se subscriptions, sponsored banners, classified ads, local business ads aur special edition campaigns sell kiye ja sakte hain. Publishers apne advertisers ko web + app visibility package offer kar sakte hain.</p>

<h3>The Up Media se contact karein</h3>
<p>The Up Media e-paper website, newspaper app, news portal, live TV setup, reporter panel aur SEO-ready publishing system banata hai. Demo, pricing aur feature planning ke liye WhatsApp karein: <strong>{WHATSAPP_NUMBER}</strong>. Call: <strong>{PHONE_NUMBER}</strong>.</p>

<p><strong>Disclaimer:</strong> Google ranking, instant indexing ya fixed traffic guarantee nahi hoti. Hum technical SEO, content structure aur best practices ke according platform setup karte hain.</p>
"""

    def _write_service_svg(self, path):
        self._write_svg(path, "E-Paper Website and App Development", "Digital Newspaper Solution", 1, "EPAPER", "WHATSAPP: 6397712918")

    def _write_blog_svg(self, path, title, keyword, index):
        self._write_svg(path, title, keyword, index, "EPAPER", "THE UP MEDIA")

    def _write_svg(self, path, title, subtitle, index, badge, footer):
        accent, bg, ink = PALETTES[(index - 1) % len(PALETTES)]
        title_lines = self._wrap_text(title, 34, 3)
        title_tspans = self._tspans(title_lines, 88, 0, 54)
        safe_title = self._escape(title)
        safe_subtitle = self._escape(subtitle)
        safe_badge = self._escape(badge)
        safe_footer = self._escape(footer)
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="675" viewBox="0 0 1200 675" role="img" aria-label="{safe_title}">
  <rect width="1200" height="675" fill="{bg}"/>
  <rect x="54" y="54" width="1092" height="567" rx="30" fill="#ffffff" stroke="{accent}" stroke-width="5"/>
  <rect x="88" y="92" width="238" height="62" rx="31" fill="{accent}"/>
  <text x="207" y="132" text-anchor="middle" font-family="Arial, sans-serif" font-size="24" font-weight="900" fill="#ffffff">{safe_badge}</text>
  <circle cx="976" cy="178" r="96" fill="{accent}" opacity="0.13"/>
  <rect x="900" y="122" width="152" height="112" rx="16" fill="{accent}"/>
  <rect x="924" y="148" width="104" height="12" fill="#ffffff"/>
  <rect x="924" y="174" width="104" height="12" fill="#ffffff"/>
  <rect x="924" y="200" width="70" height="12" fill="#ffffff"/>
  <text y="228" font-family="Georgia, serif" font-size="44" font-weight="900" fill="{ink}">
{title_tspans}
  </text>
  <text x="88" y="410" font-family="Arial, sans-serif" font-size="34" font-weight="800" fill="{accent}">{safe_subtitle}</text>
  <text x="88" y="468" font-family="Arial, sans-serif" font-size="27" font-weight="700" fill="#374151">PDF Upload | Archive | SEO URLs | Mobile App</text>
  <text x="88" y="516" font-family="Arial, sans-serif" font-size="25" fill="#4b5563">Newspaper, Magazine and Local Media Growth</text>
  <rect x="88" y="544" width="360" height="54" rx="12" fill="{accent}"/>
  <text x="268" y="579" text-anchor="middle" font-family="Arial, sans-serif" font-size="23" font-weight="800" fill="#ffffff">{safe_footer}</text>
</svg>
"""
        path.write_text(svg, encoding="utf-8")

    def _wrap_text(self, value, max_chars, max_lines):
        words = str(value).split()
        lines = []
        current = ""
        consumed = 0
        for word in words:
            candidate = f"{current} {word}".strip()
            if len(candidate) <= max_chars:
                current = candidate
                consumed += 1
                continue
            if current:
                lines.append(current)
                current = word
                consumed += 1
            else:
                lines.append(word[:max_chars])
                current = word[max_chars:]
                consumed += 1
            if len(lines) == max_lines:
                break
        if current and len(lines) < max_lines:
            lines.append(current)
        if len(lines) == max_lines and consumed < len(words):
            lines[-1] = lines[-1].rstrip(".,:;") + "..."
        return lines or [str(value)[:max_chars]]

    def _tspans(self, lines, x, first_dy, line_dy):
        return "\n".join(
            f'    <tspan x="{x}" dy="{first_dy if index == 0 else line_dy}">{self._escape(line)}</tspan>'
            for index, line in enumerate(lines)
        )

    def _escape(self, value):
        return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
