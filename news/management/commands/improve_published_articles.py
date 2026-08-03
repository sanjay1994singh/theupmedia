from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand
from django.utils.html import strip_tags
from PIL import Image, ImageDraw, ImageFont

from news.models import Article


ARTICLE_GUIDES = {
    1: {
        "angle": "मौसम अलर्ट में पाठकों को आधिकारिक चेतावनी, स्थानीय तैयारी और सावधानी समझानी है।",
        "reader_need": "लोग जानना चाहते हैं कि घर, यात्रा, खेती और रोजमर्रा की योजना कैसे सुरक्षित रखी जाए।",
        "source": "मौसम विभाग और स्थानीय प्रशासन की ताजा सलाह उपलब्ध होने पर जोड़ें",
    },
    2: {
        "angle": "जिला अस्पताल में अल्ट्रासाउंड सेवा बंद होने से गर्भवती महिलाओं और मरीजों की परेशानी पर केंद्रित रिपोर्ट।",
        "reader_need": "पाठकों को वैकल्पिक व्यवस्था, शिकायत प्रक्रिया और अस्पताल प्रबंधन से अपेक्षित जवाबदेही समझनी है।",
        "source": "अस्पताल प्रशासन, स्वास्थ्य विभाग या स्थानीय जनप्रतिनिधि का बयान उपलब्ध होने पर जोड़ें",
    },
    3: {
        "angle": "राम मंदिर दान से जुड़े आरोपों में पारदर्शिता, जांच और सार्वजनिक भरोसे का सवाल।",
        "reader_need": "लोग जानना चाहते हैं कि आरोप, जांच की मांग और संस्थागत पारदर्शिता का महत्व क्या है।",
        "source": "संबंधित संस्था, प्रशासन या जांच एजेंसी की आधिकारिक प्रतिक्रिया उपलब्ध होने पर जोड़ें",
    },
    4: {
        "angle": "वृंदावन में पुलिस कार्रवाई, चैन स्नैचिंग और स्थानीय सुरक्षा की चिंता पर संतुलित रिपोर्ट।",
        "reader_need": "पाठकों को पुलिस दावे, बरामदगी, जांच प्रक्रिया और नागरिक सावधानी की जानकारी चाहिए।",
        "source": "स्थानीय पुलिस या आधिकारिक प्रेस नोट उपलब्ध होने पर जोड़ें",
    },
    5: {
        "angle": "कोचिंग सेंटर आग की घटना में छात्र सुरक्षा, भवन मानक और जांच की जरूरत पर केंद्रित रिपोर्ट।",
        "reader_need": "परिवार और छात्र जानना चाहते हैं कि कोचिंग संस्थानों में सुरक्षा ऑडिट क्यों जरूरी है।",
        "source": "दमकल विभाग, पुलिस या प्रशासनिक जांच रिपोर्ट उपलब्ध होने पर जोड़ें",
    },
    16: {
        "angle": "पासपोर्ट फीस बदलाव को आम नागरिकों के खर्च, आवेदन तैयारी और दस्तावेज व्यवस्था से जोड़कर समझाना है।",
        "reader_need": "लोग जानना चाहते हैं कि नई फीस कब लागू होगी, किन आवेदकों पर असर पड़ेगा और आवेदन से पहले क्या चेक करें।",
        "source": "पासपोर्ट सेवा या विदेश मंत्रालय की आधिकारिक फीस सूचना उपलब्ध होने पर जोड़ें",
    },
    17: {
        "angle": "पानी संकट, देर से मानसून और शहर-किसान दोनों पर असर की व्याख्यात्मक रिपोर्ट।",
        "reader_need": "पाठकों को जल संरक्षण, स्थानीय सप्लाई, खेती और प्रशासनिक तैयारी समझनी है।",
        "source": "जल विभाग, कृषि विभाग और मौसम विभाग की स्थानीय जानकारी उपलब्ध होने पर जोड़ें",
    },
    18: {
        "angle": "मंदिर जमीन विवाद और पुजारी हत्या मामले में कानून-व्यवस्था, भूमि रिकॉर्ड और निष्पक्ष जांच पर रिपोर्ट।",
        "reader_need": "लोगों को आरोपों से अलग तथ्य, जांच प्रक्रिया और सामाजिक शांति का महत्व समझना है।",
        "source": "पुलिस, राजस्व विभाग या अदालत से उपलब्ध आधिकारिक जानकारी जोड़ें",
    },
}


class Command(BaseCommand):
    help = "Expand existing published articles into longer review-safe public-interest articles."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Save changes. Without this, only preview titles.")
        parser.add_argument("--limit", type=int, default=20)

    def handle(self, *args, **options):
        queryset = Article.objects.filter(status=Article.Status.PUBLISHED).order_by("id")[: options["limit"]]
        updated = 0
        for article in queryset:
            guide = ARTICLE_GUIDES.get(article.pk, self._default_guide(article))
            content = self._build_content(article, guide)
            word_count = len(strip_tags(content).split())
            self.stdout.write(f"{article.pk}: {article.title} -> {word_count} words")
            if not options["apply"]:
                continue

            article.content = content
            article.summary = self._summary(article, guide)
            article.meta_title = article.title[:160]
            article.meta_description = article.summary[:220]
            article.meta_keywords = self._keywords(article)
            article.image_alt_text = article.image_alt_text or article.title[:180]
            article.image_caption = article.image_caption or f"{article.title} से जुड़ी प्रतीकात्मक तस्वीर"
            article.image_credit = article.image_credit or "The Up Media"
            article.source_name = article.source_name or guide["source"]
            article.save()
            if not article.featured_image:
                self._attach_thumbnail(article)
            updated += 1
        self.stdout.write(self.style.SUCCESS(f"Updated articles: {updated}"))

    def _default_guide(self, article):
        return {
            "angle": f"{article.title} को पाठकों के लिए संदर्भ, असर और आगे की जरूरत के साथ समझाना है।",
            "reader_need": "पाठकों को साफ, उपयोगी और जिम्मेदार जानकारी चाहिए।",
            "source": "संबंधित आधिकारिक स्रोत उपलब्ध होने पर जोड़ें",
        }

    def _summary(self, article, guide):
        return (
            f"{article.title} पर यह विस्तृत रिपोर्ट मुख्य तथ्य, स्थानीय असर, पाठकों के लिए जरूरी सावधानी "
            "और आगे की संभावित कार्रवाई को सरल भाषा में समझाती है।"
        )[:220]

    def _keywords(self, article):
        parts = [article.title, article.category.name]
        if article.state:
            parts.append(article.state.name)
        if article.city:
            parts.append(article.city.name)
        parts.extend(["The Up Media", "Hindi news", "public interest"])
        return ", ".join(dict.fromkeys(part for part in parts if part))[:255]

    def _build_content(self, article, guide):
        location = ""
        if article.city and article.state:
            location = f"{article.city.name}, {article.state.name}"
        elif article.state:
            location = article.state.name
        else:
            location = "स्थानीय क्षेत्र"

        return f"""
<p><strong>{article.title}</strong> से जुड़ा मामला आम पाठकों के लिए सिर्फ एक खबर नहीं, बल्कि जवाबदेही, तैयारी और भरोसे से जुड़ा सवाल भी है। {guide['angle']} इस रिपोर्ट में उपलब्ध जानकारी को सनसनी से अलग रखकर सरल भाषा में समझाया गया है, ताकि पाठक यह जान सकें कि मामला क्यों महत्वपूर्ण है और आगे किन बातों पर ध्यान देना जरूरी होगा।</p>

<h2>मामले की मुख्य बात</h2>
<p>{article.summary} {location} से जुड़े ऐसे मामलों में सबसे जरूरी बात यह होती है कि शुरुआती सूचना और अंतिम पुष्टि के बीच फर्क रखा जाए। कई बार सोशल मीडिया, स्थानीय चर्चा और शुरुआती बयान तेजी से फैलते हैं, लेकिन जिम्मेदार रिपोर्टिंग में आधिकारिक पुष्टि, संबंधित विभाग का पक्ष और प्रभावित लोगों की वास्तविक स्थिति को साथ देखकर ही निष्कर्ष निकाला जाना चाहिए।</p>

<p>{guide['reader_need']} इसलिए यह रिपोर्ट किसी अफवाह या राजनीतिक शोर पर नहीं, बल्कि सार्वजनिक हित की जरूरत पर केंद्रित है। यदि किसी मामले में जांच चल रही है, सेवा बाधित है, प्रशासनिक निर्णय बाकी है या लोगों की सुरक्षा से जुड़ा सवाल है, तो पाठकों को यह समझना चाहिए कि आगे आने वाली आधिकारिक जानकारी खबर की दिशा बदल सकती है।</p>

<h2>लोगों पर इसका असर क्या हो सकता है</h2>
<p>ऐसी खबरों का पहला असर आम नागरिकों के भरोसे पर पड़ता है। जब शिक्षा, स्वास्थ्य, कानून-व्यवस्था, मौसम, पानी, धार्मिक संस्था, सार्वजनिक सेवा या सरकारी प्रक्रिया से जुड़ा मामला सामने आता है, तो लोग सिर्फ घटना नहीं देखते; वे यह भी देखते हैं कि जिम्मेदार संस्था कितनी जल्दी जवाब देती है, समस्या कितनी पारदर्शिता से स्वीकार की जाती है और समाधान के लिए क्या कदम उठाए जाते हैं।</p>

<p>यदि मामला सेवा बाधित होने का है, तो लोगों को वैकल्पिक व्यवस्था की जरूरत पड़ती है। यदि मामला अपराध या जांच का है, तो निष्पक्ष जांच और कानूनी प्रक्रिया पर भरोसा जरूरी हो जाता है। यदि मामला फीस, नियम या सरकारी सेवा से जुड़ा है, तो नागरिकों को स्पष्ट तारीख, शुल्क, दस्तावेज और शिकायत व्यवस्था की जानकारी चाहिए। यही वजह है कि खबर को सिर्फ घटना बताकर छोड़ देना पर्याप्त नहीं होता।</p>

<h2>प्रशासन और संबंधित विभाग से क्या अपेक्षा है</h2>
<p>संबंधित विभाग को सबसे पहले स्पष्ट और समयबद्ध सूचना देनी चाहिए। अस्पष्ट जवाब या देर से आई सफाई अक्सर भ्रम बढ़ाती है। यदि गलती हुई है, तो उसे स्वीकार कर सुधार की समयसीमा बतानी चाहिए। यदि आरोप गलत हैं, तो तथ्यों और दस्तावेजों के साथ स्थिति स्पष्ट करनी चाहिए। नागरिकों के लिए हेल्पलाइन, शिकायत ईमेल, स्थानीय अधिकारी का नाम और अगली समीक्षा की तारीख जैसी जानकारी बहुत उपयोगी होती है।</p>

<p>दूसरा जरूरी कदम रिकॉर्ड और प्रक्रिया को पारदर्शी बनाना है। अस्पताल, परीक्षा, पुलिस कार्रवाई, जमीन विवाद, मौसम चेतावनी, जल आपूर्ति या सरकारी फीस जैसे मामलों में लिखित आदेश, सार्वजनिक सूचना और नियमित अपडेट लोगों का भरोसा बढ़ाते हैं। इससे अफवाहों की जगह आधिकारिक जानकारी लेती है और विवाद कम होता है।</p>

<h2>पाठकों को क्या सावधानी रखनी चाहिए</h2>
<p>पाठकों को किसी भी वायरल पोस्ट, बिना स्रोत वाले वीडियो या अधूरी जानकारी को तुरंत सच मानने से बचना चाहिए। खबर से जुड़े दस्तावेज, आधिकारिक वेबसाइट, स्थानीय प्रशासन की सूचना और विश्वसनीय समाचार रिपोर्ट देखना बेहतर है। यदि मामला व्यक्तिगत सुरक्षा, स्वास्थ्य, परीक्षा, वित्तीय भुगतान या कानूनी कार्रवाई से जुड़ा है, तो निर्णय लेने से पहले संबंधित विभाग से पुष्टि करना जरूरी है।</p>

<p>प्रभावित लोगों को भी अपनी शिकायत लिखित रूप में दर्ज करनी चाहिए। तारीख, समय, स्थान, संबंधित अधिकारी, रसीद, फोटो, वीडियो या दस्तावेज सुरक्षित रखना आगे की कार्रवाई में मदद कर सकता है। केवल सोशल मीडिया पोस्ट करने से कई बार समस्या चर्चा में तो आ जाती है, लेकिन औपचारिक समाधान के लिए लिखित शिकायत और सही मंच जरूरी होता है।</p>

<h2>आगे क्या हो सकता है</h2>
<p>आगे की स्थिति इस बात पर निर्भर करेगी कि संबंधित विभाग या जांच एजेंसी कितनी जल्दी तथ्य सामने रखती है। यदि मामला प्रशासनिक लापरवाही का है, तो सुधारात्मक कार्रवाई, जांच रिपोर्ट और जिम्मेदारी तय होना जरूरी होगा। यदि मामला नीति या फीस बदलाव का है, तो स्पष्ट अधिसूचना और नागरिकों के लिए आसान मार्गदर्शन जरूरी होगा। यदि मामला अपराध या विवाद से जुड़ा है, तो पुलिस जांच, अदालत या संबंधित विभाग की रिपोर्ट निर्णायक होगी।</p>

<p><strong>Editorial note:</strong> यह लेख उपलब्ध जानकारी के आधार पर स्वतंत्र रूप से लिखा गया है। इसमें किसी दूसरे प्रकाशन की भाषा या पैराग्राफ संरचना का उपयोग नहीं किया गया है। नई आधिकारिक जानकारी आने पर लेख को अपडेट किया जा सकता है। संदर्भ: {guide['source']}।</p>
""".strip()

    def _attach_thumbnail(self, article):
        thumb_dir = settings.MEDIA_ROOT / "articles" / "generated"
        thumb_dir.mkdir(parents=True, exist_ok=True)
        file_path = thumb_dir / f"article-{article.pk}-thumb.jpg"

        image = Image.new("RGB", (1200, 675), "#111827")
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 1200, 675), fill="#111827")
        draw.rectangle((0, 0, 1200, 150), fill="#b91c1c")
        draw.rectangle((42, 192, 1158, 620), outline="#ef4444", width=6)
        draw.text((64, 46), "THE UP MEDIA", fill="#ffffff")
        draw.text((72, 230), article.title[:90], fill="#ffffff")
        draw.text((72, 548), article.category.name.upper(), fill="#fca5a5")
        image.save(file_path, "JPEG", quality=88, optimize=True)

        with file_path.open("rb") as image_file:
            article.featured_image.save(file_path.name, File(image_file), save=True)
