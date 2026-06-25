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
        "à¤¹à¥ˆ",
        "à¤¹à¥ˆà¤‚",
        "à¤”à¤°",
        "à¤®à¥‡à¤‚",
        "à¤•à¤¾",
        "à¤•à¥€",
        "à¤•à¥‡",
        "à¤¸à¥‡",
        "à¤ªà¤°",
        "à¤•à¥‹",
        "à¤¨à¥‡",
        "à¤²à¤¿à¤",
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
    parts = re.split(r"(?<=[.!?à¥¤])\s+", clean_text(text))
    return [part.strip() for part in parts if part.strip()][:limit]


def _topic_from_title(title):
    return re.sub(r"\s+à¤®à¤¾à¤®à¤²à¥‡ à¤®à¥‡à¤‚ à¤¨à¤¯à¤¾ à¤…à¤ªà¤¡à¥‡à¤Ÿ$", "", title).strip() or title


def _fact_points(title, summary):
    text = clean_text(summary)
    topic = Truncator(_topic_from_title(title)).chars(120)
    points = [f"{topic} à¤¸à¥‡ à¤œà¥à¤¡à¤¼à¤¾ à¤…à¤ªà¤¡à¥‡à¤Ÿ à¤¸à¤¾à¤°à¥à¤µà¤œà¤¨à¤¿à¤• à¤¸à¥à¤°à¥‹à¤¤à¥‹à¤‚ à¤®à¥‡à¤‚ à¤¸à¤¾à¤®à¤¨à¥‡ à¤†à¤¯à¤¾ à¤¹à¥ˆà¥¤"]

    numbers = re.findall(r"\b\d+[\w%/-]*\b", text)
    if numbers:
        points.append(f"à¤‰à¤ªà¤²à¤¬à¥à¤§ à¤œà¤¾à¤¨à¤•à¤¾à¤°à¥€ à¤®à¥‡à¤‚ {', '.join(numbers[:4])} à¤œà¥ˆà¤¸à¥‡ à¤¤à¤¥à¥à¤¯à¤¾à¤¤à¥à¤®à¤• à¤†à¤‚à¤•à¤¡à¤¼à¥‹à¤‚ à¤•à¤¾ à¤‰à¤²à¥à¤²à¥‡à¤– à¤¹à¥ˆ; à¤ªà¥à¤°à¤•à¤¾à¤¶à¤¨ à¤¸à¥‡ à¤ªà¤¹à¤²à¥‡ à¤‡à¤¨à¤•à¥€ à¤ªà¥à¤·à¥à¤Ÿà¤¿ à¤œà¤°à¥‚à¤°à¥€ à¤¹à¥ˆà¥¤")

    lower_text = text.lower()
    if any(word in lower_text for word in ["police", "arrest", "case", "investigation", "court", "fir", "accused"]):
        points.append("à¤®à¤¾à¤®à¤²à¤¾ à¤•à¤¾à¤¨à¥‚à¤¨-à¤µà¥à¤¯à¤µà¤¸à¥à¤¥à¤¾, à¤œà¤¾à¤‚à¤š à¤¯à¤¾ à¤ªà¥à¤°à¤¶à¤¾à¤¸à¤¨à¤¿à¤• à¤•à¤¾à¤°à¥à¤°à¤µà¤¾à¤ˆ à¤¸à¥‡ à¤œà¥à¤¡à¤¼à¤¾ à¤¹à¥‹ à¤¸à¤•à¤¤à¤¾ à¤¹à¥ˆà¥¤")
    if any(word in lower_text for word in ["hospital", "health", "doctor", "patient", "medical", "fire", "school", "student"]):
        points.append("à¤‡à¤¸ à¤…à¤ªà¤¡à¥‡à¤Ÿ à¤•à¤¾ à¤…à¤¸à¤° à¤¸à¥à¤¥à¤¾à¤¨à¥€à¤¯ à¤¸à¥‡à¤µà¤¾à¤“à¤‚, à¤¸à¥à¤°à¤•à¥à¤·à¤¾ à¤¯à¤¾ à¤†à¤® à¤²à¥‹à¤—à¥‹à¤‚ à¤•à¥€ à¤¸à¥à¤µà¤¿à¤§à¤¾ à¤ªà¤° à¤ªà¤¡à¤¼ à¤¸à¤•à¤¤à¤¾ à¤¹à¥ˆà¥¤")

    points.append("à¤†à¤§à¤¿à¤•à¤¾à¤°à¤¿à¤• à¤ªà¥à¤·à¥à¤Ÿà¤¿, à¤¸à¥à¤¥à¤¾à¤¨à¥€à¤¯ à¤¬à¤¯à¤¾à¤¨ à¤”à¤° à¤†à¤—à¥‡ à¤•à¥‡ à¤…à¤ªà¤¡à¥‡à¤Ÿ à¤•à¥‡ à¤†à¤§à¤¾à¤° à¤ªà¤° à¤–à¤¬à¤° à¤•à¥‹ à¤…à¤‚à¤¤à¤¿à¤® à¤°à¥‚à¤ª à¤¦à¥‡à¤¨à¤¾ à¤šà¤¾à¤¹à¤¿à¤à¥¤")
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

    title = _original_title(original_title)
    topic = _topic_from_title(title)
    fact_points = _fact_points(title, original_summary)
    first_fact = fact_points[0]
    source_label = source_name or "à¤¸à¤‚à¤¬à¤‚à¤§à¤¿à¤¤ à¤¸à¥à¤°à¥‹à¤¤"
    fact_list = "\n".join(f"<li>{html.escape(point)}</li>" for point in fact_points)
    source_html = (
        f'<p><strong>Reference:</strong> <a href="{html.escape(source_url)}" rel="nofollow noopener" '
        f'target="_blank">{html.escape(source_label)}</a></p>'
        if source_url
        else ""
    )

    summary = Truncator(
        f"{topic} à¤¸à¥‡ à¤œà¥à¤¡à¤¼à¥€ à¤‰à¤ªà¤²à¤¬à¥à¤§ à¤œà¤¾à¤¨à¤•à¤¾à¤°à¥€ à¤•à¥‡ à¤†à¤§à¤¾à¤° à¤ªà¤° à¤¯à¤¹ à¤–à¤¬à¤° à¤¤à¥ˆà¤¯à¤¾à¤° à¤•à¥€ à¤—à¤ˆ à¤¹à¥ˆà¥¤ à¤‡à¤¸à¤®à¥‡à¤‚ à¤®à¥à¤–à¥à¤¯ à¤¤à¤¥à¥à¤¯, "
        "à¤¸à¥à¤¥à¤¾à¤¨à¥€à¤¯ à¤¸à¤‚à¤¦à¤°à¥à¤­ à¤”à¤° à¤†à¤® à¤²à¥‹à¤—à¥‹à¤‚ à¤ªà¤° à¤¸à¤‚à¤­à¤¾à¤µà¤¿à¤¤ à¤…à¤¸à¤° à¤•à¥‹ à¤¸à¤°à¤² à¤­à¤¾à¤·à¤¾ à¤®à¥‡à¤‚ à¤¸à¤®à¤à¤¾à¤¯à¤¾ à¤—à¤¯à¤¾ à¤¹à¥ˆà¥¤"
    ).chars(220)

    content_parts = [
        f"<h2>{html.escape(title)}: à¤•à¥à¤¯à¤¾ à¤¹à¥ˆ à¤ªà¥‚à¤°à¤¾ à¤®à¤¾à¤®à¤²à¤¾</h2>",
        (
            f"<p>{html.escape(first_fact)} à¤‡à¤¸ à¤…à¤ªà¤¡à¥‡à¤Ÿ à¤¨à¥‡ à¤¸à¥à¤¥à¤¾à¤¨à¥€à¤¯ à¤¸à¥à¤¤à¤° à¤ªà¤° à¤šà¤°à¥à¤šà¤¾ à¤¬à¤¢à¤¼à¤¾à¤ˆ à¤¹à¥ˆà¥¤ "
            "The Up Media à¤¨à¥‡ à¤‰à¤ªà¤²à¤¬à¥à¤§ à¤¸à¤¾à¤°à¥à¤µà¤œà¤¨à¤¿à¤• à¤œà¤¾à¤¨à¤•à¤¾à¤°à¥€ à¤•à¥‹ à¤†à¤§à¤¾à¤° à¤¬à¤¨à¤¾à¤•à¤° à¤¯à¤¹ à¤¸à¥à¤µà¤¤à¤‚à¤¤à¥à¤° à¤¡à¥à¤°à¤¾à¤«à¥à¤Ÿ à¤¤à¥ˆà¤¯à¤¾à¤° à¤•à¤¿à¤¯à¤¾ à¤¹à¥ˆ, "
            "à¤¤à¤¾à¤•à¤¿ à¤ªà¤¾à¤ à¤•à¥‹à¤‚ à¤•à¥‹ à¤˜à¤Ÿà¤¨à¤¾ à¤•à¤¾ à¤¸à¤‚à¤¦à¤°à¥à¤­ à¤¸à¤¾à¤« à¤”à¤° à¤¸à¤°à¤² à¤­à¤¾à¤·à¤¾ à¤®à¥‡à¤‚ à¤®à¤¿à¤² à¤¸à¤•à¥‡à¥¤</p>"
        ),
        "<h3>à¤…à¤¬ à¤¤à¤• à¤¸à¤¾à¤®à¤¨à¥‡ à¤†à¤ à¤®à¥à¤–à¥à¤¯ à¤¤à¤¥à¥à¤¯</h3>",
        f"<ul>{fact_list}</ul>",
        "<h3>à¤¸à¥à¤¥à¤¾à¤¨à¥€à¤¯ à¤¸à¤‚à¤¦à¤°à¥à¤­ à¤”à¤° à¤…à¤¸à¤°</h3>",
        (
            "<p>à¤‡à¤¸ à¤¤à¤°à¤¹ à¤•à¥€ à¤–à¤¬à¤°à¥‹à¤‚ à¤•à¤¾ à¤…à¤¸à¤° à¤†à¤® à¤ªà¤¾à¤ à¤•à¥‹à¤‚, à¤¸à¥à¤¥à¤¾à¤¨à¥€à¤¯ à¤²à¥‹à¤—à¥‹à¤‚ à¤”à¤° à¤¸à¤‚à¤¬à¤‚à¤§à¤¿à¤¤ à¤ªà¤•à¥à¤·à¥‹à¤‚ à¤ªà¤° à¤ªà¤¡à¤¼ à¤¸à¤•à¤¤à¤¾ à¤¹à¥ˆà¥¤ "
            "à¤‡à¤¸à¤²à¤¿à¤ à¤¸à¤¿à¤°à¥à¤« à¤˜à¤Ÿà¤¨à¤¾ à¤¬à¤¤à¤¾à¤¨à¤¾ à¤•à¤¾à¤«à¥€ à¤¨à¤¹à¥€à¤‚ à¤¹à¥ˆ; à¤¯à¤¹ à¤¸à¤®à¤à¤¨à¤¾ à¤­à¥€ à¤œà¤°à¥‚à¤°à¥€ à¤¹à¥ˆ à¤•à¤¿ à¤‡à¤¸à¤¸à¥‡ à¤¸à¥à¤°à¤•à¥à¤·à¤¾, à¤µà¥à¤¯à¤µà¤¸à¥à¤¥à¤¾, "
            "à¤¸à¥à¤µà¤¿à¤§à¤¾, à¤œà¤¨à¤¹à¤¿à¤¤ à¤¯à¤¾ à¤¸à¥à¤¥à¤¾à¤¨à¥€à¤¯ à¤®à¤¾à¤¹à¥Œà¤² à¤ªà¤° à¤•à¥à¤¯à¤¾ à¤ªà¥à¤°à¤­à¤¾à¤µ à¤ªà¤¡à¤¼ à¤¸à¤•à¤¤à¤¾ à¤¹à¥ˆà¥¤</p>"
        ),
        "<h3>à¤ªà¥ƒà¤·à¥à¤ à¤­à¥‚à¤®à¤¿</h3>",
        (
            "<p>à¤®à¤¾à¤®à¤²à¥‡ à¤¸à¥‡ à¤œà¥à¤¡à¤¼à¥€ à¤œà¤¾à¤¨à¤•à¤¾à¤°à¥€ à¤…à¤­à¥€ à¤¸à¤¾à¤°à¥à¤µà¤œà¤¨à¤¿à¤• à¤¸à¥à¤°à¥‹à¤¤à¥‹à¤‚ à¤”à¤° à¤‰à¤ªà¤²à¤¬à¥à¤§ à¤…à¤ªà¤¡à¥‡à¤Ÿ à¤ªà¤° à¤†à¤§à¤¾à¤°à¤¿à¤¤ à¤¹à¥ˆà¥¤ "
            "à¤¸à¤‚à¤ªà¤¾à¤¦à¤•à¥€à¤¯ à¤Ÿà¥€à¤® à¤•à¥‹ à¤ªà¥à¤°à¤•à¤¾à¤¶à¤¨ à¤¸à¥‡ à¤ªà¤¹à¤²à¥‡ à¤¨à¤¾à¤®, à¤¸à¥à¤¥à¤¾à¤¨, à¤¤à¤¾à¤°à¥€à¤–, à¤¸à¤‚à¤–à¥à¤¯à¤¾ à¤”à¤° à¤†à¤§à¤¿à¤•à¤¾à¤°à¤¿à¤• à¤¬à¤¯à¤¾à¤¨ à¤œà¥ˆà¤¸à¥‡ "
            "à¤¤à¤¥à¥à¤¯à¥‹à¤‚ à¤•à¥€ à¤¦à¥‹à¤¬à¤¾à¤°à¤¾ à¤œà¤¾à¤‚à¤š à¤•à¤°à¤¨à¥€ à¤šà¤¾à¤¹à¤¿à¤à¥¤</p>"
        ),
        "<h3>à¤†à¤—à¥‡ à¤•à¥à¤¯à¤¾ à¤¦à¥‡à¤–à¤¨à¤¾ à¤œà¤°à¥‚à¤°à¥€ à¤¹à¥ˆ</h3>",
        (
            "<p>à¤†à¤—à¥‡ à¤•à¥€ à¤¸à¥à¤¥à¤¿à¤¤à¤¿ à¤¸à¤‚à¤¬à¤‚à¤§à¤¿à¤¤ à¤µà¤¿à¤­à¤¾à¤—, à¤¸à¤‚à¤¸à¥à¤¥à¤¾, à¤¸à¥à¤¥à¤¾à¤¨à¥€à¤¯ à¤ªà¥à¤°à¤¶à¤¾à¤¸à¤¨ à¤¯à¤¾ à¤†à¤§à¤¿à¤•à¤¾à¤°à¤¿à¤• à¤¸à¥à¤°à¥‹à¤¤à¥‹à¤‚ à¤¸à¥‡ à¤®à¤¿à¤²à¤¨à¥‡ à¤µà¤¾à¤²à¥€ "
            "à¤ªà¥à¤·à¥à¤Ÿà¤¿ à¤ªà¤° à¤¨à¤¿à¤°à¥à¤­à¤° à¤•à¤°à¥‡à¤—à¥€à¥¤ à¤¯à¤¦à¤¿ à¤¨à¤ à¤¤à¤¥à¥à¤¯ à¤¸à¤¾à¤®à¤¨à¥‡ à¤†à¤¤à¥‡ à¤¹à¥ˆà¤‚, à¤¤à¥‹ à¤–à¤¬à¤° à¤•à¥‹ à¤…à¤ªà¤¡à¥‡à¤Ÿ à¤•à¤¿à¤¯à¤¾ à¤œà¤¾à¤¨à¤¾ à¤šà¤¾à¤¹à¤¿à¤à¥¤</p>"
        ),
        (
            "<p><strong>Editorial note:</strong> à¤¯à¤¹ à¤¡à¥à¤°à¤¾à¤«à¥à¤Ÿ à¤®à¥‚à¤² à¤¸à¥à¤°à¥‹à¤¤ à¤•à¥€ à¤­à¤¾à¤·à¤¾, à¤ªà¥ˆà¤°à¤¾à¤—à¥à¤°à¤¾à¤« à¤•à¥à¤°à¤® à¤¯à¤¾ "
            "à¤µà¤¾à¤•à¥à¤¯ à¤¸à¤‚à¤°à¤šà¤¨à¤¾ à¤•à¥‹ à¤•à¥‰à¤ªà¥€ à¤•à¤°à¤•à¥‡ à¤¨à¤¹à¥€à¤‚ à¤¬à¤¨à¤¾à¤¯à¤¾ à¤—à¤¯à¤¾ à¤¹à¥ˆà¥¤ à¤‡à¤¸à¥‡ à¤‰à¤ªà¤²à¤¬à¥à¤§ à¤¤à¤¥à¥à¤¯à¥‹à¤‚ à¤•à¥‡ à¤†à¤§à¤¾à¤° à¤ªà¤° à¤¸à¥à¤µà¤¤à¤‚à¤¤à¥à¤° "
            "à¤¸à¤®à¤¾à¤šà¤¾à¤° à¤²à¥‡à¤– à¤•à¥‡ à¤°à¥‚à¤ª à¤®à¥‡à¤‚ à¤¤à¥ˆà¤¯à¤¾à¤° à¤•à¤¿à¤¯à¤¾ à¤—à¤¯à¤¾ à¤¹à¥ˆà¥¤</p>"
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
