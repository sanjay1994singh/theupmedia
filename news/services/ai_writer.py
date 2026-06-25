import html
import re
from dataclasses import dataclass
from html.parser import HTMLParser

from django.utils.text import Truncator

from news.slug_utils import seo_slugify


MOJIBAKE_MARKERS = ("à¤", "à¥", "â€", "â€œ", "â€", "Â")


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


def has_mojibake(value):
    value = value or ""
    return any(marker in value for marker in MOJIBAKE_MARKERS)


def repair_mojibake(value):
    value = value or ""
    if not has_mojibake(value):
        return value

    repaired = value
    for _ in range(3):
        if not has_mojibake(repaired):
            break
        previous = repaired
        repaired = _repair_once(repaired)
        if repaired == previous:
            break
    return repaired


def _repair_once(value):
    for encoding in ("latin1", "cp1252"):
        try:
            repaired = value.encode(encoding).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
        if repaired:
            return repaired

    byte_values = bytearray()
    for char in value:
        codepoint = ord(char)
        if codepoint <= 255:
            byte_values.append(codepoint)
            continue
        try:
            byte_values.extend(char.encode("cp1252"))
        except UnicodeEncodeError:
            byte_values.extend(char.encode("utf-8"))

    try:
        repaired = bytes(byte_values).decode("utf-8")
    except UnicodeDecodeError:
        return value
    return repaired or value


def clean_text(value):
    value = repair_mojibake(html.unescape(value or ""))
    parser = HTMLTextExtractor()
    parser.feed(value)
    text = repair_mojibake(parser.text() or value)
    text = text.replace("\ufffd", "").replace("□", "")
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
        "यह",
        "इस",
    }
    seen = []
    for word in words:
        normalized = clean_text(word).strip(" -_").lower()
        if len(normalized) < 3 or normalized in stop_words:
            continue
        if normalized not in seen:
            seen.append(normalized)
    return seen[:12]


def _topic_from_title(title):
    title = clean_text(title)
    title = re.sub(r"\s+मामले में नया अपडेट$", "", title).strip()
    return title or "स्थानीय अपडेट"


def _fact_points(title, summary):
    text = clean_text(summary)
    topic = Truncator(_topic_from_title(title)).chars(120)
    points = [f"{topic} से जुड़ा अपडेट सार्वजनिक स्रोतों में सामने आया है।"]

    numbers = re.findall(r"\b\d+[\w%/-]*\b", text)
    if numbers:
        points.append(
            f"उपलब्ध जानकारी में {', '.join(numbers[:4])} जैसे तथ्यात्मक आंकड़ों का उल्लेख है; "
            "प्रकाशन से पहले इनकी पुष्टि जरूरी है।"
        )

    lower_text = text.lower()
    if any(word in lower_text for word in ["police", "arrest", "case", "investigation", "court", "fir", "accused", "पुलिस", "गिरफ्तार", "जांच"]):
        points.append("मामला कानून-व्यवस्था, जांच या प्रशासनिक कार्रवाई से जुड़ा हो सकता है।")
    if any(word in lower_text for word in ["hospital", "health", "doctor", "patient", "medical", "fire", "school", "student", "अस्पताल", "स्वास्थ्य", "आग"]):
        points.append("इस अपडेट का असर स्थानीय सेवाओं, सुरक्षा या आम लोगों की सुविधा पर पड़ सकता है।")

    points.append("आधिकारिक पुष्टि, स्थानीय बयान और आगे के अपडेट के आधार पर खबर को अंतिम रूप देना चाहिए।")
    return points[:4]


def _original_title(original_title):
    title = clean_text(original_title)
    title = re.sub(r"\s*[-|:]\s*(latest|breaking|live|news)\s*$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+", " ", title).strip(" -|:")
    title = Truncator(title).chars(120)
    lower_title = title.lower()

    if any(word in lower_title for word in ["fire", "accident", "blast", "death", "मौत", "हादसा", "आग"]):
        return f"{title}: सुरक्षा व्यवस्था और जांच पर उठे सवाल"
    if any(word in lower_title for word in ["police", "arrest", "encounter", "crime", "fir", "गिरफ्तार", "पुलिस"]):
        return f"{title}: कार्रवाई के बाद स्थानीय स्तर पर चर्चा तेज"
    if any(word in lower_title for word in ["hospital", "doctor", "patient", "health", "medical", "अस्पताल", "स्वास्थ्य"]):
        return f"{title}: स्वास्थ्य सेवाओं पर असर और लोगों की परेशानी"
    if any(word in lower_title for word in ["school", "student", "exam", "college", "छात्र", "स्कूल"]):
        return f"{title}: छात्रों और अभिभावकों के लिए अहम अपडेट"
    if any(word in lower_title for word in ["weather", "rain", "heat", "storm", "मौसम", "बारिश", "गर्मी"]):
        return f"{title}: मौसम बदलाव से आम लोगों पर असर"
    if any(word in lower_title for word in ["mathura", "vrindavan", "agra", "uttar pradesh", "up", "मथुरा", "वृंदावन"]):
        return f"{title}: यूपी के स्थानीय लोगों के लिए अहम खबर"
    return f"{title}: जानिए पूरा मामला और आगे क्या हो सकता है"


def build_hindi_news_draft(original_title, original_summary="", source_name="", source_url=""):
    """Create an original review-ready Hindi draft from limited verified source facts.

    This utility deliberately does not copy source paragraph order, sentence structure,
    heading pattern, or wording. It only uses the fetched title/summary as fact inputs.
    Final publication must still be reviewed by an editor.
    """
    original_title = clean_text(original_title)
    original_summary = clean_text(original_summary)
    source_name = clean_text(source_name)

    title = clean_text(_original_title(original_title))
    topic = _topic_from_title(title)
    fact_points = [clean_text(point) for point in _fact_points(title, original_summary)]
    first_fact = fact_points[0]
    source_label = source_name or "संबंधित स्रोत"
    fact_list = "\n".join(f"<li>{html.escape(point)}</li>" for point in fact_points)
    source_html = (
        f'<p><strong>Reference:</strong> <a href="{html.escape(source_url)}" rel="nofollow noopener" '
        f'target="_blank">{html.escape(source_label)}</a></p>'
        if source_url
        else ""
    )

    summary_text = (
        f"{topic} से जुड़ी उपलब्ध जानकारी के आधार पर यह खबर तैयार की गई है। "
        "इसमें मुख्य तथ्य, स्थानीय संदर्भ और आम लोगों पर संभावित असर को सरल भाषा में समझाया गया है।"
    )
    summary = Truncator(clean_text(summary_text)).chars(220)

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
    content = repair_mojibake("\n".join(part for part in content_parts if part))
    keywords = clean_text(", ".join(_keyword_candidates(title, original_summary, source_name)))
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
