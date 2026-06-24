import html
import re
from dataclasses import dataclass
from html.parser import HTMLParser

from django.utils.text import Truncator

from news.slug_utils import seo_slugify


class HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        text = data.strip()
        if text:
            self.parts.append(text)

    def text(self):
        return " ".join(self.parts)


@dataclass(frozen=True)
class AINewsDraft:
    ai_title: str
    ai_summary: str
    ai_content: str
    source_credit: str
    source_url: str
    fact_points: list[str]
    seo_keywords: str
    slug: str
    internal_note: str


def clean_text(value):
    value = html.unescape(value or "")
    parser = HTMLTextExtractor()
    parser.feed(value)
    text = parser.text() or value
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _keyword_candidates(title, summary, source_name):
    text = f"{title} {summary} {source_name}"
    words = re.findall(r"[\w\u0900-\u097F]+", text)
    stop_words = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "this",
        "that",
        "news",
        "hai",
        "hain",
        "aur",
        "mein",
        "hindi",
        "live",
        "latest",
        "breaking",
        "है",
        "हैं",
        "और",
        "में",
        "का",
        "की",
        "के",
        "से",
        "पर",
        "को",
        "ने",
        "लिए",
    }
    seen = []
    for word in words:
        normalized = word.strip(" -_").lower()
        if len(normalized) < 3 or normalized in stop_words:
            continue
        if normalized not in seen:
            seen.append(normalized)
    return seen[:12]


def _sentences(text, limit=4):
    parts = re.split(r"(?<=[.!?।])\s+", clean_text(text))
    return [part.strip() for part in parts if part.strip()][:limit]


def _topic_from_title(title):
    return re.sub(r"\s+मामले में नया अपडेट$", "", title).strip() or title


def _fact_points(title, summary):
    text = clean_text(summary)
    topic = Truncator(_topic_from_title(title)).chars(120)
    points = [f"{topic} से जुड़ा अपडेट सार्वजनिक स्रोतों में सामने आया है।"]

    numbers = re.findall(r"\b\d+[\w%/-]*\b", text)
    if numbers:
        points.append(f"उपलब्ध जानकारी में {', '.join(numbers[:4])} जैसे तथ्यात्मक आंकड़ों का उल्लेख है; प्रकाशन से पहले इनकी पुष्टि जरूरी है।")

    lower_text = text.lower()
    if any(word in lower_text for word in ["police", "arrest", "case", "investigation", "court", "fir", "accused"]):
        points.append("मामला कानून-व्यवस्था, जांच या प्रशासनिक कार्रवाई से जुड़ा हो सकता है।")
    if any(word in lower_text for word in ["hospital", "health", "doctor", "patient", "medical", "fire", "school", "student"]):
        points.append("इस अपडेट का असर स्थानीय सेवाओं, सुरक्षा या आम लोगों की सुविधा पर पड़ सकता है।")

    points.append("आधिकारिक पुष्टि, स्थानीय बयान और आगे के अपडेट के आधार पर खबर को अंतिम रूप देना चाहिए।")
    return points[:4]


def _original_title(original_title):
    title = clean_text(original_title)
    title = re.sub(r"\s*[-|:]\s*(latest|breaking|live|news)\s*$", "", title, flags=re.IGNORECASE)
    title = Truncator(title).chars(150)
    return f"{title} मामले में नया अपडेट"


def build_hindi_news_draft(original_title, original_summary="", source_name="", source_url=""):
    """Create an original review-ready Hindi draft from limited verified source facts.

    This utility deliberately does not copy source paragraph order, sentence structure,
    heading pattern, or wording. It only uses the fetched title/summary as fact inputs.
    Final publication must still be reviewed by an editor.
    """
    original_title = clean_text(original_title)
    original_summary = clean_text(original_summary)
    source_name = clean_text(source_name)

    title = _original_title(original_title)
    topic = _topic_from_title(title)
    fact_points = _fact_points(title, original_summary)
    first_fact = fact_points[0]
    source_label = source_name or "संबंधित स्रोत"
    fact_list = "\n".join(f"<li>{html.escape(point)}</li>" for point in fact_points)
    source_html = (
        f'<p><strong>Reference:</strong> <a href="{html.escape(source_url)}" rel="nofollow noopener" '
        f'target="_blank">{html.escape(source_label)}</a></p>'
        if source_url
        else ""
    )

    summary = Truncator(
        f"{topic} से जुड़ी उपलब्ध जानकारी के आधार पर यह खबर तैयार की गई है। इसमें मुख्य तथ्य, "
        "स्थानीय संदर्भ और आम लोगों पर संभावित असर को सरल भाषा में समझाया गया है।"
    ).chars(220)

    content_parts = [
        f"<h2>{html.escape(title)}: क्या है पूरा मामला</h2>",
        (
            f"<p>{html.escape(first_fact)} इस अपडेट ने स्थानीय स्तर पर चर्चा बढ़ाई है। "
            "The Up Media ने उपलब्ध सार्वजनिक जानकारी को आधार बनाकर यह स्वतंत्र ड्राफ्ट तैयार किया है, "
            "ताकि पाठकों को घटना का संदर्भ साफ और सरल भाषा में मिल सके।</p>"
        ),
        "<h3>अब तक सामने आए मुख्य तथ्य</h3>",
        f"<ul>{fact_list}</ul>",
        "<h3>स्थानीय संदर्भ और असर</h3>",
        (
            "<p>इस तरह की खबरों का असर आम पाठकों, स्थानीय लोगों और संबंधित पक्षों पर पड़ सकता है। "
            "इसलिए सिर्फ घटना बताना काफी नहीं है; यह समझना भी जरूरी है कि इससे सुरक्षा, व्यवस्था, "
            "सुविधा, जनहित या स्थानीय माहौल पर क्या प्रभाव पड़ सकता है।</p>"
        ),
        "<h3>पृष्ठभूमि</h3>",
        (
            "<p>मामले से जुड़ी जानकारी अभी सार्वजनिक स्रोतों और उपलब्ध अपडेट पर आधारित है। "
            "संपादकीय टीम को प्रकाशन से पहले नाम, स्थान, तारीख, संख्या और आधिकारिक बयान जैसे "
            "तथ्यों की दोबारा जांच करनी चाहिए।</p>"
        ),
        "<h3>आगे क्या देखना जरूरी है</h3>",
        (
            "<p>आगे की स्थिति संबंधित विभाग, संस्था, स्थानीय प्रशासन या आधिकारिक स्रोतों से मिलने वाली "
            "पुष्टि पर निर्भर करेगी। यदि नए तथ्य सामने आते हैं, तो खबर को अपडेट किया जाना चाहिए।</p>"
        ),
        (
            "<p><strong>Editorial note:</strong> यह ड्राफ्ट मूल स्रोत की भाषा, पैराग्राफ क्रम या "
            "वाक्य संरचना को कॉपी करके नहीं बनाया गया है। इसे उपलब्ध तथ्यों के आधार पर स्वतंत्र "
            "समाचार लेख के रूप में तैयार किया गया है।</p>"
        ),
        source_html,
    ]
    content = "\n".join(part for part in content_parts if part)
    keywords = ", ".join(_keyword_candidates(title, original_summary, source_name))
    slug = seo_slugify(title)
    return AINewsDraft(
        ai_title=title,
        ai_summary=summary,
        ai_content=content,
        source_credit=source_label,
        source_url=source_url,
        fact_points=fact_points,
        seo_keywords=keywords,
        slug=slug,
        internal_note="Draft generated from source facts; editor review required.",
    )
