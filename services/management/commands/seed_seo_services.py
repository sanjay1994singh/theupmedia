from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from services.models import Service


SERVICES = [
    ("news-portal-development-company-india", "News Portal Development Company in India", "न्यूज़ पोर्टल डेवलपमेंट कंपनी", "News", "NEWS"),
    ("google-news-ready-website-development", "Google News Ready Website Development", "गूगल न्यूज़ रेडी वेबसाइट डेवलपमेंट", "News", "GNEWS"),
    ("live-tv-news-channel-setup", "Live TV News Channel Setup", "लाइव टीवी न्यूज़ चैनल सेटअप", "Live TV", "LIVE"),
    ("android-news-app-development", "Android News App Development", "एंड्रॉयड न्यूज़ ऐप डेवलपमेंट", "Mobile App", "APP"),
    ("reporter-panel-development", "Reporter Panel Development", "रिपोर्टर पैनल डेवलपमेंट", "News", "REP"),
    ("ai-thumbnail-generator-for-news", "AI Thumbnail Generator for News", "न्यूज़ के लिए AI थंबनेल जनरेटर", "AI", "AI"),
    ("ai-news-automation-system", "AI News Automation System", "AI न्यूज़ ऑटोमेशन सिस्टम", "AI", "AUTO"),
    ("epaper-solution-development", "E-Paper Solution Development", "ई-पेपर सॉल्यूशन डेवलपमेंट", "Media", "EPAPER"),
    ("school-management-software", "School Management Software", "स्कूल मैनेजमेंट सॉफ्टवेयर", "Education", "SCHOOL"),
    ("ngo-website-development", "NGO Website Development", "NGO वेबसाइट डेवलपमेंट", "Website", "NGO"),
    ("hospital-website-development", "Hospital Website Development", "हॉस्पिटल वेबसाइट डेवलपमेंट", "Website", "HOSP"),
    ("clinic-appointment-booking-system", "Clinic Appointment Booking System", "क्लिनिक अपॉइंटमेंट बुकिंग सिस्टम", "Healthcare", "CLINIC"),
    ("real-estate-property-portal", "Real Estate Property Portal", "रियल एस्टेट प्रॉपर्टी पोर्टल", "Property", "PROP"),
    ("ecommerce-website-development", "Ecommerce Website Development", "ई-कॉमर्स वेबसाइट डेवलपमेंट", "Commerce", "SHOP"),
    ("local-business-website-development", "Local Business Website Development", "लोकल बिज़नेस वेबसाइट डेवलपमेंट", "Website", "LOCAL"),
    ("restaurant-website-with-online-ordering", "Restaurant Website with Online Ordering", "रेस्टोरेंट वेबसाइट और ऑनलाइन ऑर्डरिंग", "Food", "FOOD"),
    ("hotel-booking-website-development", "Hotel Booking Website Development", "होटल बुकिंग वेबसाइट डेवलपमेंट", "Travel", "HOTEL"),
    ("travel-agency-website-development", "Travel Agency Website Development", "ट्रैवल एजेंसी वेबसाइट डेवलपमेंट", "Travel", "TRAVEL"),
    ("coaching-institute-website-development", "Coaching Institute Website Development", "कोचिंग इंस्टीट्यूट वेबसाइट डेवलपमेंट", "Education", "COACH"),
    ("online-course-lms-development", "Online Course LMS Development", "ऑनलाइन कोर्स LMS डेवलपमेंट", "Education", "LMS"),
    ("job-portal-development", "Job Portal Development", "जॉब पोर्टल डेवलपमेंट", "Portal", "JOB"),
    ("classified-ads-portal-development", "Classified Ads Portal Development", "क्लासिफाइड ऐड्स पोर्टल डेवलपमेंट", "Portal", "ADS"),
    ("directory-listing-website-development", "Directory Listing Website Development", "डायरेक्टरी लिस्टिंग वेबसाइट डेवलपमेंट", "Portal", "DIR"),
    ("matrimonial-website-development", "Matrimonial Website Development", "मैट्रिमोनियल वेबसाइट डेवलपमेंट", "Portal", "MATCH"),
    ("event-management-website-development", "Event Management Website Development", "इवेंट मैनेजमेंट वेबसाइट डेवलपमेंट", "Events", "EVENT"),
    ("political-campaign-website-development", "Political Campaign Website Development", "पॉलिटिकल कैंपेन वेबसाइट डेवलपमेंट", "Campaign", "POL"),
    ("personal-brand-portfolio-website", "Personal Brand Portfolio Website", "पर्सनल ब्रांड पोर्टफोलियो वेबसाइट", "Branding", "PORT"),
    ("corporate-business-website-development", "Corporate Business Website Development", "कॉर्पोरेट बिज़नेस वेबसाइट डेवलपमेंट", "Website", "CORP"),
    ("landing-page-development-for-ads", "Landing Page Development for Ads", "ऐड्स के लिए लैंडिंग पेज डेवलपमेंट", "Marketing", "LAND"),
    ("seo-service-for-small-business", "SEO Service for Small Business", "स्मॉल बिज़नेस SEO सर्विस", "SEO", "SEO"),
    ("technical-seo-audit-service", "Technical SEO Audit Service", "टेक्निकल SEO ऑडिट सर्विस", "SEO", "AUDIT"),
    ("local-seo-google-business-profile", "Local SEO and Google Business Profile", "लोकल SEO और Google Business Profile", "SEO", "LOCAL SEO"),
    ("content-writing-seo-blog-service", "Content Writing and SEO Blog Service", "कंटेंट राइटिंग और SEO ब्लॉग सर्विस", "Content", "BLOG"),
    ("wordpress-to-django-migration", "WordPress to Django Migration", "WordPress से Django माइग्रेशन", "Django", "MIG"),
    ("django-website-development", "Django Website Development", "Django वेबसाइट डेवलपमेंट", "Django", "DJ"),
    ("python-automation-tools", "Python Automation Tools", "Python ऑटोमेशन टूल्स", "Automation", "PY"),
    ("crm-software-development", "CRM Software Development", "CRM सॉफ्टवेयर डेवलपमेंट", "CRM", "CRM"),
    ("erp-software-development", "ERP Software Development", "ERP सॉफ्टवेयर डेवलपमेंट", "ERP", "ERP"),
    ("inventory-management-software", "Inventory Management Software", "इन्वेंटरी मैनेजमेंट सॉफ्टवेयर", "Software", "INV"),
    ("billing-invoice-software", "Billing and Invoice Software", "बिलिंग और इनवॉइस सॉफ्टवेयर", "Software", "BILL"),
    ("lead-management-system", "Lead Management System", "लीड मैनेजमेंट सिस्टम", "CRM", "LEAD"),
    ("whatsapp-business-api-integration", "WhatsApp Business API Integration", "WhatsApp Business API इंटीग्रेशन", "Automation", "WA"),
    ("payment-gateway-integration", "Payment Gateway Integration", "पेमेंट गेटवे इंटीग्रेशन", "Payment", "PAY"),
    ("api-development-and-integration", "API Development and Integration", "API डेवलपमेंट और इंटीग्रेशन", "API", "API"),
    ("web-scraping-and-data-automation", "Web Scraping and Data Automation", "वेब स्क्रैपिंग और डेटा ऑटोमेशन", "Data", "DATA"),
    ("custom-admin-panel-development", "Custom Admin Panel Development", "कस्टम एडमिन पैनल डेवलपमेंट", "Admin", "ADMIN"),
    ("mobile-responsive-website-redesign", "Mobile Responsive Website Redesign", "मोबाइल रेस्पॉन्सिव वेबसाइट रीडिज़ाइन", "Design", "UI"),
    ("website-speed-optimization", "Website Speed Optimization", "वेबसाइट स्पीड ऑप्टिमाइजेशन", "Performance", "FAST"),
    ("website-maintenance-support", "Website Maintenance and Support", "वेबसाइट मेंटेनेंस और सपोर्ट", "Support", "SUP"),
    ("gen-ai-web-app-development", "Gen AI Web App Development", "Gen AI वेब ऐप डेवलपमेंट", "AI", "GEN AI"),
]


PALETTES = [
    ("#991b1b", "#fef3c7", "#1f2937"),
    ("#0f766e", "#ecfeff", "#111827"),
    ("#1d4ed8", "#eff6ff", "#111827"),
    ("#7c2d12", "#fff7ed", "#111827"),
    ("#4c1d95", "#f5f3ff", "#111827"),
    ("#166534", "#f0fdf4", "#111827"),
]


class Command(BaseCommand):
    help = "Seed 50 SEO service pages and generate original static service images."

    def add_arguments(self, parser):
        parser.add_argument("--no-images", action="store_true", help="Only seed service records, do not generate SVG images.")

    def handle(self, *args, **options):
        image_dir = settings.BASE_DIR / "static" / "img" / "services" / "seo"
        if not options["no_images"]:
            image_dir.mkdir(parents=True, exist_ok=True)

        created = 0
        updated = 0
        for index, (slug, name, name_hi, category, icon) in enumerate(SERVICES, start=1):
            image_path = f"img/services/seo/{slug}.svg"
            if not options["no_images"]:
                self._write_svg(image_dir / f"{slug}.svg", name, name_hi, category, icon, index)
            defaults = self._service_defaults(index, slug, name, name_hi, category, icon, image_path)
            _, was_created = Service.objects.update_or_create(slug=slug, defaults=defaults)
            created += int(was_created)
            updated += int(not was_created)

        self.stdout.write(self.style.SUCCESS(f"SEO services seeded. Created: {created}, updated: {updated}"))

    def _service_defaults(self, index, slug, name, name_hi, category, icon, image_path):
        short_en = (
            f"{name} for businesses that need a fast, SEO-ready, mobile-friendly digital platform with clear enquiry flow."
        )
        short_hi = (
            f"{name_hi} सेवा उन businesses के लिए है जिन्हें SEO-ready, mobile-friendly और enquiry focused digital platform चाहिए।"
        )
        description_hi = f"""## {name_hi}

आज के digital market में {name_hi} आपके business को professional identity, search visibility और direct enquiries दिलाने में मदद करता है। हम आपका page, portal या software clean design, fast loading, mobile responsive layout और SEO structure के साथ बनाते हैं।

### इस service में क्या मिलेगा?

• SEO friendly URL और page structure
• Mobile responsive design
• WhatsApp enquiry button
• Fast loading pages
• Admin panel या content management जहां needed हो
• Sitemap, meta title, meta description और basic schema support
• Business goal के according CTA और lead flow

### किसके लिए useful है?

यह service local business, startup, institute, media brand, service provider और growing companies के लिए useful है। हम content और layout को आपके target customers के हिसाब से plan करते हैं।

### Important note

Google ranking, approval या viral reach guaranteed नहीं होती। हम Google-friendly technical setup, SEO content structure और best practices provide करते हैं; final ranking content quality, competition, backlinks, website authority और Google policies पर depend करती है।

### Contact

इस service की demo, cost और timeline जानने के लिए WhatsApp करें: +91 6397712918."""

        description_en = f"""## {name}

{name} helps your business build a professional online presence with SEO-ready structure, mobile responsive design, and a clear enquiry journey. The setup is planned for long-term organic visibility, user trust, and practical business growth.

### Key features

• SEO-friendly page and URL structure
• Mobile-first responsive UI
• Fast loading implementation
• WhatsApp enquiry integration
• Admin panel or content workflow where required
• Sitemap, meta tags, and structured content blocks
• Conversion-focused calls to action

### Why choose The Up Media

The Up Media builds Django websites, automation tools, media platforms, AI-powered workflows, and business software with practical project-based experience. Each service page is designed to be useful for users, not just search engines.

### Disclaimer

We do not promise guaranteed Google ranking, Google News approval, viral traffic, or fixed-time approval. We provide SEO-ready technical setup and content guidance based on best practices; results depend on competition, content quality, domain authority, and search engine policies.

WhatsApp: +91 6397712918"""

        return {
            "name": name,
            "name_hi": name_hi,
            "short_description": short_en,
            "short_description_hi": short_hi,
            "description": description_en,
            "description_hi": description_hi,
            "image_path": image_path,
            "icon_label": icon,
            "starting_price": "Custom quote",
            "delivery_time": "Depends on scope",
            "is_featured": index <= 12,
            "is_active": True,
            "display_order": 100 + index,
            "meta_title": f"{name} | The Up Media",
            "meta_description": short_en[:220],
            "meta_keywords": f"{name}, {name_hi}, {category}, Django website, SEO service, The Up Media",
        }

    def _write_svg(self, path, name, name_hi, category, icon, index):
        accent, bg, ink = PALETTES[(index - 1) % len(PALETTES)]
        safe_name = self._escape(name)
        safe_category = self._escape(category)
        safe_icon = self._escape(icon)
        name_tspans = self._tspans(self._wrap_text(name, max_chars=32, max_lines=2), 92, 0, 54)
        hi_tspans = self._tspans(self._wrap_text("प्रोफेशनल डिजिटल सर्विस", max_chars=34, max_lines=2), 92, 0, 42)
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="675" viewBox="0 0 1200 675" role="img" aria-label="{safe_name}">
  <rect width="1200" height="675" fill="{bg}"/>
  <rect x="52" y="52" width="1096" height="571" rx="28" fill="#ffffff" stroke="{accent}" stroke-width="5"/>
  <rect x="86" y="86" width="214" height="64" rx="32" fill="{accent}"/>
  <text x="193" y="128" text-anchor="middle" font-family="Arial, sans-serif" font-size="28" font-weight="800" fill="#ffffff">{safe_category}</text>
  <circle cx="982" cy="180" r="92" fill="{accent}" opacity="0.12"/>
  <circle cx="982" cy="180" r="58" fill="{accent}"/>
  <text x="982" y="191" text-anchor="middle" font-family="Arial, sans-serif" font-size="28" font-weight="900" fill="#ffffff">{safe_icon}</text>
  <text y="236" font-family="Georgia, serif" font-size="46" font-weight="900" fill="{ink}">
{name_tspans}
  </text>
  <text y="346" font-family="Arial, sans-serif" font-size="32" font-weight="800" fill="{accent}">
{hi_tspans}
  </text>
  <text x="92" y="442" font-family="Arial, sans-serif" font-size="28" font-weight="700" fill="#374151">SEO-ready website, app and software solutions</text>
  <text x="92" y="494" font-family="Arial, sans-serif" font-size="26" fill="#4b5563">Django | Automation | AI | Business Growth</text>
  <rect x="92" y="522" width="310" height="58" rx="12" fill="{accent}"/>
  <text x="247" y="560" text-anchor="middle" font-family="Arial, sans-serif" font-size="24" font-weight="800" fill="#ffffff">WhatsApp: 6397712918</text>
  <text x="812" y="560" font-family="Arial, sans-serif" font-size="30" font-weight="900" fill="{accent}">THE UP MEDIA</text>
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
