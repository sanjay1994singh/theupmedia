from django.db import migrations


SERVICE_SLUG = "mobile-news-live-tv-react-native-app-development"


SERVICE_DATA = {
    "name": "Mobile News Live TV React Native App Development",
    "name_hi": "मोबाइल न्यूज़ लाइव टीवी ऐप डेवलपमेंट",
    "slug": SERVICE_SLUG,
    "short_description": (
        "React Native mobile news app with Live TV, shorts, video upload, categories, state-city news, "
        "reporter workflow, push-ready structure, and Django backend integration."
    ),
    "short_description_hi": (
        "React Native न्यूज़ ऐप जिसमें Live TV, Shorts, Video Upload, State-City News, "
        "Reporter Workflow और Django Backend Integration मिलता है।"
    ),
    "description_hi": """## मोबाइल न्यूज़ लाइव टीवी ऐप डेवलपमेंट

आज के समय में local journalist, digital news channel, YouTube news creator और media brand को सिर्फ website से काम नहीं चलता। Readers और viewers ज्यादा समय mobile par spend करते हैं, इसलिए एक professional **Mobile News Live TV App** आपकी brand value, audience retention और subscription sale को मजबूत बना सकता है।

The Up Media आपके news portal के लिए React Native based mobile app बनाता है, जो Android app, Live TV player, shorts feed, video upload, news categories और Django backend के साथ connected रहता है।

### यह service किन लोगों के लिए है?

• Local news channel owners
• Journalists और reporters
• YouTube news channels
• Digital media startups
• State-city based news portals
• Religious, political, crime, health और local update platforms

### App में क्या-क्या features मिल सकते हैं?

✓ Live TV player
✓ News categories
✓ Breaking news updates
✓ State और city wise news
✓ Shorts video feed
✓ Direct video upload
✓ YouTube video support
✓ Reporter/admin login
✓ Profile section
✓ Social share options
✓ Advertisement placement
✓ Django backend API integration
✓ Fast mobile UI
✓ Future push notification support

### React Native News App क्यों बेहतर है?

React Native app fast development, smooth mobile experience और single codebase से Android focused launch में मदद करता है। अगर आपका backend Django में है, तो same news, live TV content, categories और media data app में API के through show किया जा सकता है।

### SEO और Business Benefit

इस तरह की app service उन users को target करती है जो Google पर search करते हैं:

• News app development company in India
• Live TV news app development
• React Native news app developer
• Mobile news portal app
• Local news channel app
• Reporter panel news app
• News shorts app development

### Subscription Sale के लिए उपयोग

आप इस app को monthly या yearly subscription model में बेच सकते हैं। Client को app + backend + live TV + support package दिया जा सकता है। The Up Media आपके लिए custom plan, feature list और payment workflow भी setup कर सकता है।

### Important Note

Google ranking, Play Store approval, viral reach या fixed result guaranteed नहीं होता। हम SEO-ready page, app architecture, backend integration और professional technical setup provide करते हैं। Final result content quality, marketing, competition और platform policies पर depend करता है।

### Contact

अपना Mobile News Live TV App, News Portal App या Reporter App बनवाने के लिए WhatsApp करें: +91 6397712918""",
    "description": """## Mobile News Live TV React Native App Development

The Up Media builds mobile-first news and live TV applications for journalists, media brands, YouTube news channels, and local news portals. This service is designed for businesses that want a professional mobile app connected with a Django backend and a practical subscription-ready workflow.

### Core App Features

• React Native mobile app
• Live TV player
• Category-wise news feed
• State and city-wise content
• Shorts-style video feed
• Direct video upload support
• YouTube video support
• Reporter/admin workflow
• Profile and user sections
• Social sharing
• Advertisement placement
• Django API integration
• Fast and responsive mobile UI
• Push notification-ready architecture

### Who Should Buy This Service?

This service is useful for local journalists, news agencies, digital media startups, YouTube news channels, religious channels, political news groups, and city-level news brands that want to launch a mobile news platform.

### Business Use Case

You can sell this mobile news app as a subscription package to local news brands. Plans can include app setup, backend panel, Live TV management, shorts/video upload, support, maintenance, and optional custom features.

### SEO Keywords Covered

News app development company, React Native news app, Live TV news app, mobile news portal app, local news channel app, reporter panel app, news shorts app development, Django news app backend.

### Disclaimer

We do not guarantee Google ranking, app store approval, viral reach, or fixed-time approval. We provide professional development, SEO-ready structure, and technical best practices.

WhatsApp: +91 6397712918""",
    "image_path": "img/services/seo/mobile-news-live-tv-react-native-app-development.svg",
    "icon_label": "NEWS APP",
    "starting_price": "Custom quote",
    "delivery_time": "Depends on features",
    "is_featured": True,
    "is_active": True,
    "display_order": 4,
    "meta_title": "Mobile News Live TV React Native App Development | News App Company",
    "meta_description": (
        "React Native mobile news app with Live TV, shorts, video upload, reporter workflow, "
        "state-city news and Django backend integration."
    ),
    "meta_keywords": (
        "mobile news live tv app, react native news app, news app development company, "
        "live tv news app, reporter panel app, django news app backend, news shorts app"
    ),
}


def add_service(apps, schema_editor):
    Service = apps.get_model("services", "Service")
    Service.objects.update_or_create(slug=SERVICE_SLUG, defaults=SERVICE_DATA)


def remove_service(apps, schema_editor):
    Service = apps.get_model("services", "Service")
    Service.objects.filter(slug=SERVICE_SLUG).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("services", "0008_service_image_path"),
    ]

    operations = [
        migrations.RunPython(add_service, remove_service),
    ]

