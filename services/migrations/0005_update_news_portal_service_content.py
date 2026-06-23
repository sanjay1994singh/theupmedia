from django.db import migrations


NEWS_PORTAL_CONTENT = {
    "name": "News Portal Development Company in India",
    "name_hi": "न्यूज़ पोर्टल डेवलपमेंट कंपनी इन इंडिया",
    "short_description": (
        "News portal website, Android app, live TV streaming, reporter panel, "
        "Google News-ready SEO, and AI-powered media automation solutions."
    ),
    "short_description_hi": (
        "न्यूज़ वेबसाइट, मोबाइल ऐप, लाइव टीवी, रिपोर्टर पैनल, Google News-ready SEO "
        "और AI मीडिया ऑटोमेशन के साथ complete news portal solution."
    ),
    "description_hi": """आज के डिजिटल युग में हर समाचार संस्थान, पत्रकार, यूट्यूब न्यूज़ चैनल और मीडिया संगठन को अपनी डिजिटल पहचान की आवश्यकता है। एक प्रोफेशनल न्यूज़ पोर्टल न केवल आपकी खबरों को लाखों लोगों तक पहुंचाता है बल्कि Google Search, Google News और सोशल मीडिया से ट्रैफिक प्राप्त करने में भी मदद करता है।

News Portal Website क्यों जरूरी है?

• अपनी मीडिया ब्रांड पहचान बनाएं
• Google News में शामिल होने का अवसर
• विज्ञापनों से आय अर्जित करें
• Android App के माध्यम से पाठकों तक पहुंचें
• Live TV Streaming की सुविधा
• Reporter Login और Multi User Management

एक प्रोफेशनल न्यूज़ पोर्टल में क्या होना चाहिए?

1. News Management System
• Category Wise News
• Breaking News
• Trending News
• Video News

2. SEO Friendly Features
• SEO URLs
• News Sitemap
• Meta Tags
• Schema Markup

3. Mobile App Integration
• Android App
• Push Notifications
• Fast Loading Experience

4. Live TV Streaming
• YouTube Live Integration
• HLS Streaming
• Breaking News Ticker

5. AI Powered Features
• AI Thumbnail Generator
• AI SEO Generator
• AI News Summary
• AI News Shorts Generator

News Portal Development Cost

लागत आपके फीचर्स और आवश्यकताओं पर निर्भर करती है। एक बेसिक न्यूज़ वेबसाइट से लेकर एडवांस AI आधारित मीडिया प्लेटफॉर्म तक विभिन्न विकल्प उपलब्ध हैं।

Why Choose TheUPMedia?

TheUPMedia पत्रकारों, मीडिया संस्थानों और न्यूज़ चैनलों के लिए Complete Media Technology Solutions प्रदान करता है।

हमारी सेवाएं:

✓ News Website Development
✓ Android News App
✓ Live TV Setup
✓ Google News Ready Platform
✓ AI News Automation
✓ E-Paper Solution
✓ Reporter Panel
✓ Advertisement Management

Contact Us

अपना न्यूज़ पोर्टल, मोबाइल ऐप या Live TV प्लेटफॉर्म बनवाने के लिए आज ही संपर्क करें।

Demo: theupmedia.in
WhatsApp: +91 6397712918""",
    "description": """In today's digital age, every news organization, journalist, YouTube news channel, and media brand needs a strong digital presence. A professional news portal helps you publish faster, build audience trust, and grow traffic from Google Search, Google News, and social media.

Why do you need a News Portal Website?

• Build your own media brand identity
• Get ready for Google News opportunities
• Earn through advertisements and sponsored content
• Reach readers through Android app integration
• Add live TV streaming for real-time coverage
• Manage reporters and multiple users from one admin panel

Professional News Portal Features

1. News Management System
• Category wise news publishing
• Breaking news
• Trending news
• Video news

2. SEO Friendly Features
• SEO URLs
• News sitemap
• Meta tags
• Schema markup

3. Mobile App Integration
• Android app
• Push notifications
• Fast loading experience

4. Live TV Streaming
• YouTube Live integration
• HLS streaming
• Breaking news ticker

5. AI Powered Features
• AI thumbnail generator
• AI SEO generator
• AI news summary
• AI news shorts generator

News Portal Development Cost

The cost depends on your required features. We can build a basic news website, an advanced media platform, or an AI-powered news publishing system.

Why Choose TheUPMedia?

TheUPMedia provides complete media technology solutions for journalists, media organizations, and news channels.

Our Services:

✓ News website development
✓ Android news app
✓ Live TV setup
✓ Google News-ready platform
✓ AI news automation
✓ E-paper solution
✓ Reporter panel
✓ Advertisement management

Contact Us

Contact us today to build your news portal, mobile app, or live TV platform.

Demo: theupmedia.in
WhatsApp: +91 6397712918""",
    "icon_label": "News",
    "starting_price": "Custom quote",
    "delivery_time": "7-20 days",
    "is_featured": True,
    "display_order": 2,
    "meta_title": "News Portal Development Company in India - Website, App, Live TV & AI",
    "meta_description": (
        "TheUPMedia builds SEO-ready news portal websites, Android apps, live TV, "
        "reporter panels, Google News-ready platforms, and AI media solutions."
    ),
    "meta_keywords": (
        "news portal development company in India, news website development, "
        "Android news app, live TV news portal, AI news automation, Google News ready website"
    ),
}


def update_news_portal_service(apps, schema_editor):
    Service = apps.get_model("services", "Service")
    Service.objects.update_or_create(
        slug="news-portal-development",
        defaults=NEWS_PORTAL_CONTENT,
    )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("services", "0004_seed_hindi_service_content"),
    ]

    operations = [
        migrations.RunPython(update_news_portal_service, noop_reverse),
    ]
