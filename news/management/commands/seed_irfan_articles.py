from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.management.base import BaseCommand
from django.utils import timezone
from PIL import Image, ImageDraw

from news.models import Article, Category
from news.slug_utils import seo_slugify, unique_article_slug


IRFAN_TOPICS = [
    (
        "मोहम्मद इरफान की वायरल आवाज: जंतर मंतर से उठी मजदूरों और छात्रों की बात",
        "इरफान के वायरल होने की वजह सिर्फ भाषण नहीं, बल्कि लोकतंत्र, मजदूरी और गरिमा पर उनकी साफ समझ थी।",
    ),
    (
        "क्या मोहम्मद इरफान सच में गरीब परिवार से आते हैं: उपलब्ध रिपोर्ट क्या बताती हैं",
        "उनके घर, काम और आय से जुड़ी मीडिया रिपोर्ट्स को सावधानी से पढ़ना जरूरी है, ताकि संवेदनशील विषय को सनसनी न बनाया जाए।",
    ),
    (
        "इरफान सरकार के सामने कौन से सवाल रख सकते हैं: मजदूर अधिकार से नशे तक",
        "उनकी बातों में असंगठित मजदूर, पुलिस जवाबदेही और कमजोर वर्गों की रोजमर्रा की परेशानी शामिल दिखती है।",
    ),
    (
        "क्या लोग मोहम्मद इरफान को follow कर सकते हैं: वायरल चेहरे से जनआवाज तक",
        "लोकप्रियता और नेतृत्व अलग चीजें हैं; इरफान के मामले में भरोसा उनके अनुभव और भाषा से बना।",
    ),
    (
        "जंतर मंतर आंदोलन में इरफान की भूमिका: राजनीति से अलग एक आम नागरिक की कहानी",
        "वह किसी बड़े संगठन के नेता नहीं, लेकिन उनकी बातों ने protest narrative को human angle दिया।",
    ),
    (
        "दिल्ली की बस्तियों में नशे का सवाल: क्या बच्चों और युवाओं पर असर पड़ सकता है",
        "इरफान द्वारा उठाई गई drug concern को public health, policing और community protection के संदर्भ में समझना चाहिए।",
    ),
    (
        "क्या राजनीतिक दल गरीब मजदूरों की आवाज पर्याप्त सुन रहे हैं",
        "इरफान की लोकप्रियता इस सवाल को सामने लाती है कि political messaging में informal workers की जगह कितनी है।",
    ),
    (
        "संविधान की प्रस्तावना पढ़ने वाले इरफान से क्या सीख मिलती है",
        "Formal education के बिना भी constitutional awareness कैसे बन सकती है, यह कहानी civic education के लिए अहम है।",
    ),
    (
        "राहुल गांधी की इरफान से मुलाकात का राजनीतिक संदेश क्या है",
        "मुलाकात को केवल फोटो-op नहीं, बल्कि marginalised youth और labour dignity की politics के संदर्भ में देखना चाहिए।",
    ),
    (
        "इरफान की कहानी और भारत का युवा माहौल: गुस्सा, उम्मीद और जवाबदेही",
        "पेपर leak, रोजगार, महंगाई और श्रमिक असुरक्षा के बीच इरफान जैसी आवाजें larger public mood दिखा सकती हैं।",
    ),
]


class Command(BaseCommand):
    help = "Create 10 review-safe scheduled articles about Mohammad Irfan's viral civic voice."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--start-date", help="YYYY-MM-DD. Default: tomorrow.")

    def handle(self, *args, **options):
        category, _ = Category.objects.get_or_create(
            name="Politics",
            defaults={"slug": seo_slugify("Politics"), "is_active": True},
        )
        start_date = timezone.localdate() + timezone.timedelta(days=1)
        if options["start_date"]:
            start_date = timezone.datetime.fromisoformat(options["start_date"]).date()
        created = 0
        skipped = 0
        author = get_user_model().objects.filter(is_superuser=True).order_by("id").first()
        for index, (title, angle) in enumerate(IRFAN_TOPICS):
            day = index // 2
            hour = 11 if index % 2 == 0 else 19
            local_dt = timezone.datetime.combine(
                start_date + timezone.timedelta(days=day),
                timezone.datetime.min.time().replace(hour=hour),
            )
            published_at = timezone.make_aware(local_dt, timezone.get_current_timezone())
            self.stdout.write(f"{index + 1:02d}. scheduled -> {published_at:%Y-%m-%d %H:%M}")
            if not options["apply"]:
                continue
            if Article.objects.filter(title=title).exists():
                skipped += 1
                continue
            summary = (
                f"{title} पर यह लेख उपलब्ध रिपोर्टों, सार्वजनिक बयानों और सामाजिक संदर्भ के आधार पर "
                "तथ्य और सवालों को संतुलित तरीके से समझाता है।"
            )[:220]
            article = Article.objects.create(
                title=title,
                slug=unique_article_slug(Article, title),
                category=category,
                summary=summary,
                content=self._content(title, angle),
                status=Article.Status.PUBLISHED,
                published_at=published_at,
                source_name="India Today, The Lallantop, NDTV and public statements around Rahul Gandhi's visit",
                source_url="https://www.indiatoday.in/india/story/mohammad-irfan-jantar-mantar-cjp-protest-viral-interview-lallantop-rahul-gandhi-meets-2957429-2026-07-27",
                image_alt_text=title[:180],
                image_caption=f"{title} से जुड़ी प्रतीकात्मक तस्वीर",
                image_credit="The Up Media",
                meta_title=title[:160],
                meta_description=summary,
                meta_keywords="Mohammad Irfan, Jantar Mantar, CJP protest, Rahul Gandhi, workers rights, Delhi, The Up Media",
                author=author,
                reviewed_by=author,
                fact_checked_by=author,
            )
            self._attach_thumbnail(article)
            created += 1
        self.stdout.write(self.style.SUCCESS(f"Created scheduled articles: {created}, skipped duplicates: {skipped}"))

    def _content(self, title, angle):
        return f"""
<p><strong>{title}</strong> हाल के दिनों में जंतर मंतर से निकली उस आवाज को समझने की कोशिश है, जिसने सोशल मीडिया पर लाखों लोगों का ध्यान खींचा। उपलब्ध मीडिया रिपोर्टों के अनुसार मोहम्मद इरफान दिल्ली के सावदा जे जे कॉलोनी क्षेत्र से जुड़े करीब 35 वर्षीय hawker/daily-wage worker हैं। वह औपचारिक शिक्षा से बहुत आगे नहीं बढ़ पाए, लेकिन उन्होंने संविधान, लोकतंत्र और मजदूर अधिकारों पर अपनी समझ YouTube और Google voice search जैसी तकनीक से विकसित करने की बात कही है।</p>

<h2>इरफान क्यों चर्चा में आए</h2>
<p>{angle} जंतर मंतर पर CJP movement और exam irregularities से जुड़े protest के दौरान उनके वीडियो वायरल हुए। रिपोर्टों में बताया गया कि उन्होंने संविधान की प्रस्तावना, लोकतंत्र, गरीबी और असंगठित मजदूरों की स्थिति पर साफ और भावनात्मक बात रखी। यही वजह रही कि उनकी छवि किसी scripted political speaker की नहीं, बल्कि जीवन के अनुभव से बोल रहे आम नागरिक की बनी।</p>

<p>यहां सावधानी जरूरी है। किसी वायरल व्यक्ति को तुरंत “नेता” या “मसीहा” बना देना उतना ही गलत हो सकता है जितना उसकी बातों को केवल इसलिए खारिज करना कि वह गरीब पृष्ठभूमि से आता है। इरफान की चर्चा का असली महत्व इस बात में है कि एक informal worker भी लोकतंत्र और अधिकारों पर गंभीर राय रख सकता है।</p>

<h2>क्या वह सच में गरीब पृष्ठभूमि से आते हैं</h2>
<p>मीडिया रिपोर्टों में इरफान को hawker, ice seller या daily-wage worker के रूप में बताया गया है। कुछ रिपोर्टों में उनके Delhi की Savda JJ Colony में रहने, अधूरे बने घर और सीमित औपचारिक शिक्षा का उल्लेख है। इन विवरणों के आधार पर इतना कहा जा सकता है कि उपलब्ध सार्वजनिक रिपोर्टें उन्हें आर्थिक रूप से कमजोर या working-class background से जोड़ती हैं। हालांकि किसी व्यक्ति की निजी आर्थिक स्थिति का अंतिम प्रमाण केवल स्वतंत्र दस्तावेजी जांच से ही तय किया जा सकता है।</p>

<p>इसलिए जिम्मेदार भाषा यही होगी कि “उपलब्ध मीडिया रिपोर्टों के अनुसार” वह गरीब/मजदूर पृष्ठभूमि से आते हैं। इसे अपमान या दया का विषय नहीं, बल्कि representation का सवाल माना जाना चाहिए।</p>

<h2>क्या वह सरकार के सामने सही बात रख सकते हैं</h2>
<p>किसी भी लोकतंत्र में सवाल पूछने का अधिकार केवल पढ़े-लिखे, पदधारी या अमीर लोगों तक सीमित नहीं होता। अगर कोई व्यक्ति मजदूरी, महंगाई, शिक्षा, नशे, पुलिस कार्रवाई या कमजोर वर्गों की परेशानी पर अपने अनुभव से बात करता है, तो वह democratic conversation का हिस्सा है। इरफान सरकार के सामने policy draft नहीं रख सकते, लेकिन वह ground reality, सवाल और pain points जरूर रख सकते हैं।</p>

<p>उनकी बातों का मूल्य इस बात में है कि वे उन वर्गों की चिंता सामने ला सकते हैं जो रोज काम करते हैं, कम कमाते हैं और public debate में अक्सर कम सुने जाते हैं। सरकार का काम ऐसे संकेतों को सुनना और उन्हें policy feedback में बदलना है।</p>

<h2>क्या लोग उन्हें follow कर सकते हैं</h2>
<p>लोग किसी viral face को follow कर सकते हैं, लेकिन blind following से बचना चाहिए। इरफान की बातों को सुनना, मजदूर अधिकार और संविधान पर चर्चा करना अच्छी बात है। लेकिन किसी भी व्यक्ति के हर दावे को तथ्य मानने से पहले source, context और evidence देखना जरूरी है। उनका महत्व एक citizen voice के रूप में है, न कि बिना जांच के अंतिम authority के रूप में।</p>

<h2>दिल्ली में नशे का सवाल और बच्चों की सुरक्षा</h2>
<p>रिपोर्टों के अनुसार इरफान ने drug-related शिकायतों और police action पर सवाल उठाए। ऐसे दावे संवेदनशील होते हैं और इन्हें verified crime data या police statement के बिना अंतिम तथ्य नहीं कहा जा सकता। फिर भी यह सच है कि किसी भी urban settlement में नशे की उपलब्धता बच्चों और युवाओं के लिए गंभीर public health और law-and-order risk बन सकती है।</p>

<p>अगर किसी इलाके में drugs आसानी से मिलती हैं, तो बच्चे स्कूल छोड़ने, हिंसा, स्वास्थ्य समस्या, मानसिक तनाव और अपराधी network के संपर्क जैसे जोखिमों में फंस सकते हैं। इसका समाधान केवल पुलिस कार्रवाई नहीं है; community reporting, de-addiction support, school counselling, youth sports spaces और parents awareness भी जरूरी है।</p>

<h2>क्या political parties गरीबों पर पर्याप्त ध्यान नहीं दे रहीं</h2>
<p>यह कहना कि सभी political parties गरीबों को पूरी तरह ignore करती हैं, बहुत व्यापक दावा होगा। लेकिन इरफान की लोकप्रियता यह जरूर दिखाती है कि मजदूर, hawker, slum residents और informal workers की रोजमर्रा की समस्या को ज्यादा स्पष्ट political attention चाहिए। चुनाव में गरीबों का नाम लिया जाता है, पर उनकी dignity, wages, housing, policing और health concerns पर लगातार काम कम दिखाई देता है।</p>

<p>अगर दल वास्तव में ऐसे वर्गों को सुनना चाहते हैं, तो उन्हें speeches से आगे बढ़कर local grievance camps, legal aid, labour registration, social security और addiction prevention जैसे ठोस कदमों पर काम करना होगा।</p>

<h2>निष्कर्ष</h2>
<p>मोहम्मद इरफान की कहानी viral fame से ज्यादा citizen voice की कहानी है। वह कोई स्थापित नेता नहीं हैं, लेकिन उनकी बातों ने यह याद दिलाया कि लोकतंत्र में संविधान की भाषा सिर्फ किताबों की चीज नहीं, बल्कि मजदूर की रोजी, छात्र की परीक्षा और बच्चे की सुरक्षा से भी जुड़ी है। उनकी बातों से सहमत या असहमत हुआ जा सकता है, लेकिन उन्हें सुनना भारत के public debate को थोड़ा ज्यादा ईमानदार बना सकता है।</p>

<p><strong>Editorial note:</strong> यह लेख उपलब्ध सार्वजनिक रिपोर्टों और बयानों के आधार पर स्वतंत्र रूप से लिखा गया है। इरफान की आर्थिक स्थिति, स्थानीय drug claims या political impact जैसे पहलुओं को अंतिम तथ्य नहीं, बल्कि रिपोर्टेड information और public-interest questions के रूप में प्रस्तुत किया गया है।</p>
""".strip()

    def _attach_thumbnail(self, article):
        thumb_dir = Path(settings.MEDIA_ROOT) / "articles" / "irfan"
        thumb_dir.mkdir(parents=True, exist_ok=True)
        file_path = thumb_dir / f"irfan-{article.pk}-thumb.jpg"
        image = Image.new("RGB", (1200, 675), "#111827")
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 1200, 675), fill="#111827")
        draw.rectangle((0, 0, 1200, 155), fill="#b91c1c")
        draw.rectangle((46, 195, 1154, 615), outline="#ef4444", width=7)
        draw.text((66, 50), "THE UP MEDIA", fill="#ffffff")
        draw.text((76, 245), "MOHAMMAD IRFAN", fill="#ffffff")
        draw.text((76, 310), "Jantar Mantar Voice", fill="#fca5a5")
        draw.text((76, 548), article.category.name.upper(), fill="#ffffff")
        image.save(file_path, "JPEG", quality=88, optimize=True)
        with file_path.open("rb") as image_file:
            article.featured_image.save(file_path.name, File(image_file), save=True)
