from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from blog.models import BlogPost


BLOGS = [
    ("live-news-tv-app-development-company", "Live News TV App Development Company for Digital News Channels", "Live News TV App"),
    ("live-tv-news-channel-app-development", "Live TV News Channel App Development: Complete Guide for Publishers", "News Channel App"),
    ("youtube-live-news-app-setup", "YouTube Live News App Setup for Local Media and Digital Channels", "YouTube Live App"),
    ("direct-video-upload-news-tv-app", "Direct Video Upload News TV App: Features, Workflow and Benefits", "Video News App"),
    ("live-tv-streaming-app-for-news-portal", "Live TV Streaming App for News Portal and Media Websites", "Live TV Streaming App"),
    ("android-live-news-tv-app", "Android Live News TV App Development for Hindi News Channels", "Android Live TV App"),
    ("live-news-app-with-breaking-news-ticker", "Live News App with Breaking News Ticker and Channel Branding", "Breaking News Ticker"),
    ("news-tv-app-with-lower-third-graphics", "News TV App with Lower Third Graphics for Professional Broadcast Look", "Lower Third Graphics"),
    ("live-tv-app-with-reporter-panel", "Live TV App with Reporter Panel for Local News Teams", "Reporter Panel App"),
    ("live-news-video-app-seo-guide", "Live News Video App SEO Guide for Search and Social Growth", "Video App SEO"),
    ("live-tv-app-for-youtube-news-channel", "Live TV App for YouTube News Channel: Website, App and Player Setup", "YouTube News Channel App"),
    ("live-news-tv-dashboard-development", "Live News TV Dashboard Development with Video, Ticker and Logo Controls", "Live TV Dashboard"),
    ("news-channel-mobile-app-cost-india", "News Channel Mobile App Cost in India: Features and Budget Planning", "News App Cost"),
    ("live-tv-app-with-autoplay-playlist", "Live TV App with Autoplay Playlist for News Videos and Live Streams", "Autoplay Playlist"),
    ("hls-m3u8-live-news-streaming-app", "HLS and M3U8 Live News Streaming App for Professional Channels", "HLS News Streaming"),
    ("live-news-app-for-local-journalists", "Live News App for Local Journalists, Reporters and Media Brands", "Local News App"),
    ("news-tv-app-with-push-notifications", "News TV App with Push Notifications for Breaking Updates", "Push Notification App"),
    ("live-news-app-with-ads-management", "Live News App with Ads Management for Revenue Growth", "News App Ads"),
    ("multi-video-news-tv-app", "Multi Video News TV App for Live, Recorded and Playlist Content", "Multi Video App"),
    ("live-tv-app-for-hindi-news-website", "Live TV App for Hindi News Website: Design, Speed and SEO", "Hindi Live TV App"),
    ("news-broadcast-app-development", "News Broadcast App Development for Digital Media Companies", "News Broadcast App"),
    ("live-tv-player-for-news-website", "Live TV Player for News Website with Channel Overlay and Ticker", "Live TV Player"),
    ("news-channel-app-with-admin-panel", "News Channel App with Admin Panel for Easy Content Management", "News App Admin Panel"),
    ("live-news-app-social-sharing", "Live News App Social Sharing Setup for Facebook, WhatsApp and Telegram", "Live News Sharing"),
    ("live-tv-app-performance-optimization", "Live TV App Performance Optimization for Fast Mobile Viewing", "Live TV Performance"),
    ("live-news-app-thumbnail-and-poster", "Live News App Thumbnail and Poster Strategy for Better Clicks", "Video Thumbnail"),
    ("live-tv-app-security-checklist", "Live TV App Security Checklist for News Publishers", "Live TV Security"),
    ("live-news-app-google-indexing", "Live News App Google Indexing: Pages, Video SEO and Internal Links", "Live App Indexing"),
    ("custom-live-tv-app-vs-template", "Custom Live TV App vs Template: Which Is Better for News Channels?", "Custom Live TV App"),
    ("best-live-news-tv-app-developer-india", "Best Live News TV App Developer in India: What Media Owners Should Check", "Live TV Developer"),
]


TOPIC_DETAILS = {
    "live-news-tv-app-development-company": "Media owners ko aisi company chahiye jo app, website, live player, dashboard aur SEO ko ek complete system ke roop me build kare.",
    "live-tv-news-channel-app-development": "News channel app me live stream, recorded video, category pages, alerts aur share-friendly detail pages ka proper workflow hona chahiye.",
    "youtube-live-news-app-setup": "YouTube live ko app aur website me embed karte waqt player settings, public URL, thumbnail aur fallback experience carefully handle karna hota hai.",
    "direct-video-upload-news-tv-app": "Direct video upload option un channels ke liye useful hai jo YouTube ke bina apni recorded bulletins ya special reports publish karna chahte hain.",
    "live-tv-streaming-app-for-news-portal": "Existing news portal ke sath live TV streaming app add karne se readers ko text news ke sath video updates bhi milte hain.",
    "android-live-news-tv-app": "Android app Hindi news audience tak fast reach banata hai, especially jab push notifications aur live player smooth ho.",
    "live-news-app-with-breaking-news-ticker": "Ticker app ko professional news-channel look deta hai, lekin text readable aur speed controlled honi chahiye.",
    "news-tv-app-with-lower-third-graphics": "Lower-third graphics headline, breaking tag aur news identity ko live broadcast style me show karte hain.",
    "live-tv-app-with-reporter-panel": "Reporter panel se field reporters video, image, text aur location updates submit kar sakte hain, editor approval ke sath.",
    "live-news-video-app-seo-guide": "Video SEO ke liye clean title, description, transcript, poster image aur internal links important signals create karte hain.",
    "live-tv-app-for-youtube-news-channel": "YouTube channel owners app ke through apne viewers ko direct live player, articles aur notifications de sakte hain.",
    "live-news-tv-dashboard-development": "Dashboard me video source, ticker text, logo, lower third, playlist aur ads controls ek jagah hone chahiye.",
    "news-channel-mobile-app-cost-india": "Cost features par depend karti hai: live player, admin panel, push alerts, ads, API, app design aur hosting.",
    "live-tv-app-with-autoplay-playlist": "Autoplay playlist live stream ke baad next video chalakar viewer engagement maintain karne me help karti hai.",
    "hls-m3u8-live-news-streaming-app": "HLS/M3U8 streaming professional channels ke liye scalable option hota hai, especially jab traffic zyada ho.",
    "live-news-app-for-local-journalists": "Local journalists ke liye app brand identity, video publishing aur direct audience connection ka strong tool ban sakta hai.",
    "news-tv-app-with-push-notifications": "Push notifications breaking news ko turant readers tak pahunchati hain, lekin overuse se users app mute kar sakte hain.",
    "live-news-app-with-ads-management": "Ads management app monetization ke liye जरूरी है, पर ad placement viewing experience खराब नहीं करना चाहिए.",
    "multi-video-news-tv-app": "Multi video app live, direct upload aur playlist content ko ek channel-like experience me organize karta hai.",
    "live-tv-app-for-hindi-news-website": "Hindi news websites ke liye readable font, low data usage, fast player aur simple navigation बहुत important हैं.",
    "news-broadcast-app-development": "Broadcast app digital-first media companies ko professional video presence aur audience retention देता है.",
    "live-tv-player-for-news-website": "Live TV player me responsive frame, mute controls, overlay behavior aur fallback link सही होना चाहिए.",
    "news-channel-app-with-admin-panel": "Admin panel simple होगा तो non-technical team भी video, ticker, logo और articles manage कर पाएगी.",
    "live-news-app-social-sharing": "Social sharing setup में article/video URL public, preview image सही और caption clear होना चाहिए.",
    "live-tv-app-performance-optimization": "Fast mobile viewing के लिए compressed assets, caching, optimized player और lightweight pages जरूरी हैं.",
    "live-news-app-thumbnail-and-poster": "Thumbnail viewer का पहला impression बनाता है; इसलिए image clear, relevant और non-misleading होनी चाहिए.",
    "live-tv-app-security-checklist": "Admin access, upload validation, HTTPS, backups और user roles live TV app security के basic pillars हैं.",
    "live-news-app-google-indexing": "Google indexing के लिए public pages, sitemap, schema, internal links और original content support देते हैं.",
    "custom-live-tv-app-vs-template": "Custom app ज्यादा flexible होता है, जबकि template जल्दी launch हो सकता है; decision budget और long-term plan पर depend करता है.",
    "best-live-news-tv-app-developer-india": "Developer choose करते समय portfolio, support, app speed, SEO knowledge और media workflow experience जरूर check करें.",
}


PALETTES = [
    ("#b91c1c", "#fff7ed", "#111827"),
    ("#0f766e", "#ecfeff", "#111827"),
    ("#1d4ed8", "#eff6ff", "#111827"),
    ("#7c2d12", "#fef3c7", "#111827"),
    ("#581c87", "#faf5ff", "#111827"),
    ("#14532d", "#f0fdf4", "#111827"),
]


class Command(BaseCommand):
    help = "Seed 30 SEO blogs for live news TV app and live TV setup services."

    def add_arguments(self, parser):
        parser.add_argument("--no-images", action="store_true", help="Only seed blog records, do not generate SVG images.")

    def handle(self, *args, **options):
        image_dir = settings.MEDIA_ROOT / "blog" / "live-tv-app-seo"
        if not options["no_images"]:
            image_dir.mkdir(parents=True, exist_ok=True)

        created = 0
        updated = 0
        now = timezone.now()
        for index, (slug, title, keyword) in enumerate(BLOGS, start=1):
            image_name = f"{slug}.svg"
            image_rel_path = f"blog/live-tv-app-seo/{image_name}"
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
                "meta_keywords": f"{keyword}, live news tv app, live tv setup, news channel app, video news app, The Up Media",
                "canonical_url": "",
                "published_at": now - timedelta(days=index),
            }
            _, was_created = BlogPost.objects.update_or_create(slug=slug, defaults=defaults)
            created += int(was_created)
            updated += int(not was_created)

        self.stdout.write(self.style.SUCCESS(f"Live TV SEO blogs ready. Created: {created}, updated: {updated}"))

    def _excerpt(self, keyword):
        return (
            f"{keyword} guide for news channels, journalists and media brands planning a live TV app, "
            "video news workflow and SEO-ready digital broadcasting platform."
        )

    def _content(self, slug, title, keyword):
        topic_detail = TOPIC_DETAILS[slug]
        return f"""
<h2>{title}</h2>
<p>Live news TV app आज के digital media business के लिए बहुत important हो चुका है। सिर्फ website पर article publish करना काफी नहीं है; readers अब video updates, live stream, breaking ticker और mobile app experience भी expect करते हैं। {keyword} सही planning के साथ बनाया जाए तो media brand को professional identity और better audience engagement मिल सकता है।</p>

<p>{topic_detail}</p>

<h3>Live News TV App क्यों जरूरी है?</h3>
<p>Local news channels, YouTube news creators, journalists और media organizations को एक ऐसा app चाहिए जहां live TV, direct videos, latest articles, push notifications और social sharing एक ही जगह available हो। इससे audience app में वापस आती है और brand recall मजबूत होता है।</p>

<h3>Important Features</h3>
<ul>
  <li>YouTube Live, HLS/M3U8 या direct video upload support</li>
  <li>Breaking news ticker और lower-third headline graphics</li>
  <li>Channel logo overlay और professional live indicator</li>
  <li>Admin dashboard for video, ticker, logo and playlist controls</li>
  <li>News articles, categories, state-city pages and search</li>
  <li>Push notifications for breaking updates</li>
  <li>SEO-friendly web pages, sitemap and share thumbnails</li>
  <li>Advertisement and sponsored campaign slots</li>
</ul>

<h3>SEO और Google Visibility कैसे plan करें?</h3>
<p>Live TV app के साथ public web pages भी जरूरी हैं। हर video, article और service page का clean title, meta description, schema-ready content, image thumbnail और internal linking होना चाहिए। Google ranking guaranteed नहीं होती, लेकिन technical SEO, fast loading और useful content से discovery improve होती है।</p>

<h3>Hindi News Channel के लिए खास ध्यान</h3>
<p>Hindi audience mobile पर ज्यादा active रहती है। इसलिए app lightweight, fast और readable होना चाहिए। Hindi headlines, clear thumbnails, easy WhatsApp sharing और low-data friendly video playback user experience को better बनाते हैं।</p>

<h3>The Up Media कैसे मदद करता है?</h3>
<p>The Up Media news portals, live TV dashboards, Android news apps, reporter panels, AI news workflows, e-paper systems और social sharing setup build करता है। हमारा focus practical media technology पर है, ताकि आपकी team daily news publishing और video broadcasting easily manage कर सके।</p>

<h3>Important Disclaimer</h3>
<p>Google ranking, Google News approval, app viral growth या fixed-time indexing guaranteed नहीं होती। हम SEO-ready technical setup, content structure और best practices provide करते हैं; final result content quality, competition, audience trust और platform policies पर depend करता है।</p>

<p><strong>Contact:</strong> Live news TV app, news channel app या live TV setup बनवाने के लिए WhatsApp करें: +91 6397712918</p>
"""

    def _write_svg(self, path, title, keyword, index):
        accent, bg, ink = PALETTES[(index - 1) % len(PALETTES)]
        title_lines = self._wrap_text(title, max_chars=34, max_lines=3)
        title_tspans = self._tspans(title_lines, 88, 0, 54)
        safe_title = self._escape(title)
        safe_keyword = self._escape(keyword)
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="675" viewBox="0 0 1200 675" role="img" aria-label="{safe_title}">
  <rect width="1200" height="675" fill="{bg}"/>
  <rect x="54" y="54" width="1092" height="567" rx="30" fill="#ffffff" stroke="{accent}" stroke-width="5"/>
  <rect x="88" y="92" width="230" height="62" rx="31" fill="{accent}"/>
  <text x="203" y="132" text-anchor="middle" font-family="Arial, sans-serif" font-size="25" font-weight="900" fill="#ffffff">LIVE TV</text>
  <circle cx="978" cy="180" r="92" fill="{accent}" opacity="0.13"/>
  <circle cx="978" cy="180" r="58" fill="{accent}"/>
  <text x="978" y="192" text-anchor="middle" font-family="Arial, sans-serif" font-size="22" font-weight="900" fill="#ffffff">NEWS</text>
  <text y="224" font-family="Georgia, serif" font-size="44" font-weight="900" fill="{ink}">
{title_tspans}
  </text>
  <text x="88" y="402" font-family="Arial, sans-serif" font-size="34" font-weight="800" fill="{accent}">{safe_keyword}</text>
  <text x="88" y="468" font-family="Arial, sans-serif" font-size="27" font-weight="700" fill="#374151">Live TV app | News channel dashboard | Video SEO</text>
  <text x="88" y="516" font-family="Arial, sans-serif" font-size="25" fill="#4b5563">Android App | YouTube Live | Direct Video | Ticker</text>
  <rect x="88" y="544" width="360" height="54" rx="12" fill="{accent}"/>
  <text x="268" y="579" text-anchor="middle" font-family="Arial, sans-serif" font-size="23" font-weight="800" fill="#ffffff">WHATSAPP: 6397712918</text>
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
        return (
            str(value)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
