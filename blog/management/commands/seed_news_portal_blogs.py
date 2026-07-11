from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from blog.models import BlogPost


BLOGS = [
    ("news-portal-development-company-india", "News Portal Development Company in India: Complete Guide for Media Brands", "News Portal Development"),
    ("news-website-development-cost-india", "News Website Development Cost in India: Features, Budget and Planning", "News Website Cost"),
    ("google-news-ready-website-guide", "Google News Ready Website: Technical Setup and Editorial Guidelines", "Google News Ready Website"),
    ("live-tv-news-channel-setup-guide", "Live TV News Channel Setup for Digital Media Platforms", "Live TV Setup"),
    ("android-news-app-development-guide", "Android News App Development: Push Notifications, Speed and Reader Experience", "Android News App"),
    ("reporter-panel-for-news-portal", "Reporter Panel for News Portal: Multi User Publishing Workflow", "Reporter Panel"),
    ("news-seo-strategy-for-local-media", "News SEO Strategy for Local Media Websites in India", "News SEO"),
    ("news-sitemap-and-rss-for-ranking", "News Sitemap, XML Sitemap and RSS: Why Every News Website Needs Them", "News Sitemap"),
    ("schema-markup-for-news-articles", "Schema Markup for News Articles: SEO Basics for Publishers", "News Schema"),
    ("fast-loading-news-website", "Fast Loading News Website: Performance Tips for Better User Experience", "Website Speed"),
    ("mobile-friendly-news-portal", "Mobile Friendly News Portal: Design Tips for Hindi News Readers", "Mobile News Portal"),
    ("hindi-news-website-seo", "Hindi News Website SEO: How to Structure Content for Search Visibility", "Hindi News SEO"),
    ("local-news-portal-for-city-updates", "Local News Portal for City Updates: Categories, State and City Pages", "Local News Portal"),
    ("digital-media-business-model", "Digital Media Business Model: Ads, Sponsored Posts and Reader Growth", "Media Business"),
    ("ai-news-automation-workflow", "AI News Automation Workflow: Drafts, Review and Editorial Safety", "AI News Automation"),
    ("ai-thumbnail-generator-for-news", "AI Thumbnail Generator for News: Better Visuals for Articles and Social Media", "AI Thumbnail"),
    ("epaper-solution-for-news-portal", "E-Paper Solution for News Portal: PDF Upload, Archive and Reader Experience", "E-Paper Solution"),
    ("breaking-news-ticker-for-website", "Breaking News Ticker for Website: UX, Speed and Editorial Control", "Breaking News Ticker"),
    ("facebook-auto-post-for-news-website", "Facebook Auto Post for News Website: Safe Setup with Page Publishing", "Facebook Auto Post"),
    ("telegram-channel-auto-share-news", "Telegram Channel Auto Share for News Articles: Setup and Best Practices", "Telegram News"),
    ("whatsapp-news-sharing-safe-workflow", "WhatsApp News Sharing Workflow: Groups, Manual Sharing and Anti-Spam Safety", "WhatsApp News"),
    ("news-portal-admin-panel-features", "News Portal Admin Panel Features Every Publisher Should Have", "Admin Panel"),
    ("seo-friendly-url-for-hindi-news", "SEO Friendly URL for Hindi News Articles: Slug and Canonical Tips", "SEO URL"),
    ("social-share-thumbnail-for-news", "Social Share Thumbnail for News: Open Graph Image Best Practices", "Social Thumbnail"),
    ("google-indexing-for-news-articles", "Google Indexing for News Articles: Sitemap, Internal Links and Crawl Signals", "Google Indexing"),
    ("news-website-security-checklist", "News Website Security Checklist for Editors and Publishers", "Website Security"),
    ("django-news-portal-development", "Django News Portal Development: Why Django Works Well for Media Websites", "Django News Portal"),
    ("content-management-for-news-team", "Content Management for News Team: Editor, Author and Reporter Roles", "News CMS"),
    ("monetize-news-website-with-ads", "How to Monetize a News Website with Ads and Sponsored Campaigns", "News Monetization"),
    ("choose-best-news-portal-developer", "How to Choose the Best News Portal Developer for Your Media Business", "News Developer"),
]


PALETTES = [
    ("#991b1b", "#fff7ed", "#111827"),
    ("#0f766e", "#ecfeff", "#111827"),
    ("#1d4ed8", "#eff6ff", "#111827"),
    ("#7c2d12", "#fef3c7", "#111827"),
    ("#4c1d95", "#f5f3ff", "#111827"),
    ("#166534", "#f0fdf4", "#111827"),
]


TOPIC_DETAILS = {
    "news-portal-development-company-india": "इस page का focus उन media owners पर है जो एक complete digital newsroom बनाना चाहते हैं। Website, admin panel, SEO setup, category pages, ads और social sharing को एक ही workflow में जोड़ना जरूरी होता है।",
    "news-website-development-cost-india": "News website cost सिर्फ design पर depend नहीं करती। Categories, reporter panel, live TV, app integration, hosting, security और SEO automation जैसे features budget को decide करते हैं।",
    "google-news-ready-website-guide": "Google News ready setup में clean URLs, author details, publishing dates, sitemap, original reporting और policy-safe content बहुत important होते हैं। Approval guarantee नहीं होती, लेकिन technical readiness strong होनी चाहिए।",
    "live-tv-news-channel-setup-guide": "Live TV setup local news channels को professional look देता है। YouTube live, direct video upload, ticker, logo overlay और lower-third graphics से viewer experience बेहतर होता है।",
    "android-news-app-development-guide": "Android news app से loyal readers तक push notifications और fast updates पहुँचते हैं। App lightweight, category-wise और share-friendly होना चाहिए ताकि daily readership बढ़ सके।",
    "reporter-panel-for-news-portal": "Reporter panel से field reporters अपनी खबर, photo और location submit कर सकते हैं। Editor approval workflow रखने से गलत या incomplete content publish होने से बचता है।",
    "news-seo-strategy-for-local-media": "Local media SEO में city, district, state और topic pages बहुत काम आते हैं। Regular updates, internal links और Hindi search intent को समझकर content publish करना जरूरी है।",
    "news-sitemap-and-rss-for-ranking": "News sitemap और RSS feed search engines और readers दोनों के लिए fresh content discovery आसान बनाते हैं। Large news websites के लिए यह technical SEO का basic हिस्सा है।",
    "schema-markup-for-news-articles": "Schema markup से search engines article title, image, date, author और publisher को better समझते हैं। यह ranking guarantee नहीं करता, लेकिन structured understanding में मदद करता है।",
    "fast-loading-news-website": "Fast loading news website reader retention और crawl efficiency दोनों के लिए important है। Compressed images, caching, optimized CSS/JS और clean templates performance improve करते हैं।",
    "mobile-friendly-news-portal": "News readers का बड़ा हिस्सा mobile पर आता है। Responsive menu, readable Hindi font, proper image ratio और easy share buttons mobile experience को मजबूत बनाते हैं।",
    "hindi-news-website-seo": "Hindi SEO में clear headings, natural Hindi-English mix, readable Devanagari content और search-friendly summaries बहुत जरूरी हैं। Mojibake या broken font content ranking और trust दोनों खराब करता है।",
    "local-news-portal-for-city-updates": "City updates वाले portal में local categories, police, health, business, education और public issues की अलग coverage होनी चाहिए। इससे local search queries target होती हैं।",
    "digital-media-business-model": "Digital media business ads, sponsored posts, service promotions, subscriptions और local partnerships पर build हो सकता है। Website को monetization-ready बनाना शुरुआत से जरूरी है।",
    "ai-news-automation-workflow": "AI workflow का सही use draft support के लिए होना चाहिए, direct copied publishing के लिए नहीं। Editor review, fact checking और source credit हमेशा जरूरी रहते हैं।",
    "ai-thumbnail-generator-for-news": "AI thumbnails article clicks और social share visibility improve कर सकते हैं। लेकिन misleading images से बचना चाहिए और image article context से related होनी चाहिए।",
    "epaper-solution-for-news-portal": "E-paper solution newspapers और magazines को PDF archive, date-wise browsing और mobile reader experience देता है। इससे पुराने editions भी searchable बन सकते हैं।",
    "breaking-news-ticker-for-website": "Breaking news ticker homepage और live TV section में urgent updates highlight करता है। इसे controlled और readable रखना चाहिए ताकि page cluttered न लगे।",
    "facebook-auto-post-for-news-website": "Facebook auto post में page token, public article URL, proper Open Graph image और timeout-safe retry logic जरूरी है। Post तभी भेजना चाहिए जब article URL live हो।",
    "telegram-channel-auto-share-news": "Telegram channel sharing fast news distribution के लिए useful है। Caption, link और image के साथ channel subscribers को instant update मिल सकता है।",
    "whatsapp-news-sharing-safe-workflow": "WhatsApp groups में safe sharing के लिए manual approval, delay और category-wise targeting बेहतर है। Spam-style automation account risk बढ़ा सकता है।",
    "news-portal-admin-panel-features": "Strong admin panel में article editor, media upload, SEO fields, category control, user roles, ads and publishing status clearly available होने चाहिए।",
    "seo-friendly-url-for-hindi-news": "Hindi news URLs readable Roman slugs या clean category paths के साथ बेहतर share होते हैं। Duplicate slug और broken URL से social preview और indexing में problem आती है।",
    "social-share-thumbnail-for-news": "Social share thumbnail Open Graph tags से control होता है। Correct image size, absolute URL और clean article metadata Facebook/WhatsApp preview को बेहतर बनाते हैं।",
    "google-indexing-for-news-articles": "Indexing के लिए sitemap, internal links, fast server response, original content और regular crawling signals important हैं। हर URL manual request करना scalable तरीका नहीं है।",
    "news-website-security-checklist": "News websites पर admin security, strong passwords, backups, HTTPS, file validation और role-based permissions जरूरी हैं ताकि publishing system safe रहे।",
    "django-news-portal-development": "Django news portal structured models, admin customization, authentication, sitemap and reusable templates के कारण media projects के लिए practical choice हो सकता है।",
    "content-management-for-news-team": "News team CMS में reporter, editor, admin और reader roles अलग होने चाहिए। Approval queue और revision control quality maintain करने में help करते हैं।",
    "monetize-news-website-with-ads": "Ads monetization के लिए clean ad slots, policy pages, fast pages और original content जरूरी होते हैं। AdSense approval immediate या guaranteed नहीं होता।",
    "choose-best-news-portal-developer": "Best developer चुनते समय सिर्फ low price न देखें। SEO knowledge, performance, admin workflow, support और previous media project experience भी check करें।",
}


class Command(BaseCommand):
    help = "Seed 30 SEO blogs about news portal and news website development with original images."

    def add_arguments(self, parser):
        parser.add_argument("--no-images", action="store_true", help="Only seed blog records, do not generate SVG images.")

    def handle(self, *args, **options):
        image_dir = settings.MEDIA_ROOT / "blog" / "news-portal-seo"
        if not options["no_images"]:
            image_dir.mkdir(parents=True, exist_ok=True)

        created = 0
        updated = 0
        now = timezone.now()
        for index, (slug, title, keyword) in enumerate(BLOGS, start=1):
            image_name = f"{slug}.svg"
            image_rel_path = f"blog/news-portal-seo/{image_name}"
            if not options["no_images"]:
                self._write_svg(image_dir / image_name, title, keyword, index)

            excerpt = self._excerpt(keyword)
            defaults = {
                "title": title,
                "excerpt": excerpt,
                "content": self._content(slug, title, keyword),
                "featured_image": image_rel_path,
                "image_alt_text": f"{title} - The Up Media",
                "focus_keyword": keyword,
                "status": BlogPost.Status.PUBLISHED,
                "is_featured": index <= 6,
                "meta_title": f"{title} | The Up Media",
                "meta_description": excerpt[:220],
                "meta_keywords": f"{keyword}, news portal, news website development, digital media, SEO, The Up Media",
                "canonical_url": "",
                "published_at": now - timedelta(days=index),
            }
            _, was_created = BlogPost.objects.update_or_create(slug=slug, defaults=defaults)
            created += int(was_created)
            updated += int(not was_created)

        self.stdout.write(self.style.SUCCESS(f"News portal SEO blogs ready. Created: {created}, updated: {updated}"))

    def _excerpt(self, keyword):
        return (
            f"{keyword} guide for media brands, journalists and local businesses planning an SEO-ready news website "
            "with fast loading pages, clean structure and practical growth strategy."
        )

    def _content(self, slug, title, keyword):
        topic_detail = TOPIC_DETAILS[slug]
        return f"""
<h2>{title}</h2>
<p>आज digital media तेजी से बदल रहा है। News portal या news website सिर्फ articles publish करने का platform नहीं है; यह brand identity, search visibility, reader trust और business enquiry का strong channel बन सकता है। {keyword} को सही planning, clean technology और editorial workflow के साथ बनाना जरूरी है।</p>
<p>{topic_detail}</p>

<h3>News website क्यों जरूरी है?</h3>
<p>Journalists, YouTube news channels, local media teams और digital publishers को एक ऐसी website चाहिए जहां वे news, images, videos, categories, state-city pages और SEO metadata को manage कर सकें। इससे readers को organized content मिलता है और search engines को website structure समझने में मदद मिलती है।</p>

<h3>Important features</h3>
<ul>
  <li>SEO-friendly URLs, title tags और meta descriptions</li>
  <li>News sitemap, XML sitemap और RSS feed</li>
  <li>Fast mobile responsive design</li>
  <li>Category, state और city-wise news structure</li>
  <li>Social sharing thumbnails for Facebook, WhatsApp and X</li>
  <li>Reporter, author and editor workflow</li>
  <li>Advertisement slots and sponsored content planning</li>
</ul>

<h3>SEO planning कैसे करें?</h3>
<p>हर important service, category और local topic के लिए dedicated page बनाना long-term SEO strategy में मदद करता है। Content useful, original और updated होना चाहिए। Internal linking, clean navigation, schema markup और image optimization भी जरूरी हैं।</p>

<h3>Hindi news website के लिए खास ध्यान</h3>
<p>Hindi readers mobile पर ज्यादा active होते हैं, इसलिए font readability, image loading, share buttons और simple navigation बहुत important हैं। Hindi content के लिए slug, meta description और summary को carefully optimize करना चाहिए ताकि page user और search engine दोनों के लिए clear रहे।</p>

<h3>The Up Media कैसे मदद करता है?</h3>
<p>The Up Media Django-based news portal, live TV setup, reporter panel, Google-friendly technical SEO, AI draft workflow, e-paper solution और social sharing setup provide करता है। हमारा focus practical publishing system बनाना है जो editorial team के daily workflow को आसान करे।</p>

<h3>Important disclaimer</h3>
<p>Google ranking, Google News approval, viral reach या fixed-time indexing guaranteed नहीं होती। हम SEO-ready technical setup, content structure और best practices provide करते हैं; final results content quality, competition, website authority और search engine policies पर depend करते हैं।</p>

<p><strong>Contact:</strong> News portal या news website बनवाने के लिए WhatsApp करें: +91 6397712918</p>
"""

    def _write_svg(self, path, title, keyword, index):
        accent, bg, ink = PALETTES[(index - 1) % len(PALETTES)]
        safe_title = self._escape(title)
        safe_keyword = self._escape(keyword)
        title_lines = self._wrap_title(title, max_chars=42, max_lines=2)
        title_tspans = "\n".join(
            f'    <tspan x="88" dy="{0 if line_index == 0 else 64}">{self._escape(line)}</tspan>'
            for line_index, line in enumerate(title_lines)
        )
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="675" viewBox="0 0 1200 675" role="img" aria-label="{safe_title}">
  <rect width="1200" height="675" fill="{bg}"/>
  <rect x="54" y="54" width="1092" height="567" rx="30" fill="#ffffff" stroke="{accent}" stroke-width="5"/>
  <rect x="88" y="92" width="240" height="62" rx="31" fill="{accent}"/>
  <text x="208" y="132" text-anchor="middle" font-family="Arial, sans-serif" font-size="26" font-weight="900" fill="#ffffff">NEWS SEO</text>
  <text y="242" font-family="Georgia, serif" font-size="50" font-weight="900" fill="{ink}">
{title_tspans}
  </text>
  <text x="88" y="382" font-family="Arial, sans-serif" font-size="36" font-weight="800" fill="{accent}">{safe_keyword}</text>
  <text x="88" y="458" font-family="Arial, sans-serif" font-size="27" font-weight="700" fill="#374151">SEO-ready news website strategy</text>
  <text x="88" y="508" font-family="Arial, sans-serif" font-size="25" fill="#4b5563">Django | Google-friendly structure | Media growth</text>
  <circle cx="978" cy="180" r="92" fill="{accent}" opacity="0.13"/>
  <circle cx="978" cy="180" r="58" fill="{accent}"/>
  <text x="978" y="192" text-anchor="middle" font-family="Arial, sans-serif" font-size="24" font-weight="900" fill="#ffffff">BLOG</text>
  <rect x="88" y="524" width="320" height="58" rx="12" fill="{accent}"/>
  <text x="248" y="562" text-anchor="middle" font-family="Arial, sans-serif" font-size="24" font-weight="800" fill="#ffffff">THE UP MEDIA</text>
</svg>
"""
        path.write_text(svg, encoding="utf-8")

    def _wrap_title(self, title, max_chars, max_lines):
        words = str(title).split()
        lines = []
        current = ""
        consumed = 0
        for word in words:
            next_line = f"{current} {word}".strip()
            if len(next_line) <= max_chars:
                current = next_line
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
        return lines or [str(title)[:max_chars]]

    def _escape(self, value):
        return (
            str(value)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
