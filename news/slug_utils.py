import re
import uuid

from django.template.defaultfilters import slugify
from django.utils import timezone


INDEPENDENT_VOWELS = {
    "अ": "a",
    "आ": "aa",
    "इ": "i",
    "ई": "ee",
    "उ": "u",
    "ऊ": "oo",
    "ऋ": "ri",
    "ए": "e",
    "ऐ": "ai",
    "ओ": "o",
    "औ": "au",
}

CONSONANTS = {
    "क": "k",
    "ख": "kh",
    "ग": "g",
    "घ": "gh",
    "ङ": "ng",
    "च": "ch",
    "छ": "chh",
    "ज": "j",
    "झ": "jh",
    "ञ": "ny",
    "ट": "t",
    "ठ": "th",
    "ड": "d",
    "ढ": "dh",
    "ण": "n",
    "त": "t",
    "थ": "th",
    "द": "d",
    "ध": "dh",
    "न": "n",
    "प": "p",
    "फ": "ph",
    "ब": "b",
    "भ": "bh",
    "म": "m",
    "य": "y",
    "र": "r",
    "ल": "l",
    "व": "v",
    "श": "sh",
    "ष": "sh",
    "स": "s",
    "ह": "h",
    "क्ष": "ksh",
    "त्र": "tr",
    "ज्ञ": "gy",
}

VOWEL_SIGNS = {
    "ा": "a",
    "ि": "i",
    "ी": "ee",
    "ु": "u",
    "ू": "oo",
    "ृ": "ri",
    "े": "e",
    "ै": "ai",
    "ो": "o",
    "ौ": "au",
}

SPECIAL_SIGNS = {
    "ं": "n",
    "ँ": "n",
    "ः": "h",
    "़": "",
    "्": "",
}

COMMON_NEWS_WORDS = {
    "यूपी": "up",
    "यू पी": "up",
    "बिहार": "bihar",
    "उत्तर प्रदेश": "uttar pradesh",
    "उत्तर भारत": "uttar bharat",
    "भारत": "bharat",
    "समेत": "samet",
    "मौसम": "mausam",
    "अलर्ट": "alert",
    "आंधी": "aandhi",
    "बारिश": "barish",
    "बरसात": "barsat",
    "लू": "loo",
    "गर्मी": "garmi",
    "खतरा": "khatra",
    "बड़ा": "bada",
    "बड़ी": "badi",
    "बड़ी": "badi",
    "दोहरा": "dohra",
    "और": "aur",
    "में": "mein",
    "का": "ka",
    "की": "ki",
    "के": "ke",
    "से": "se",
    "पर": "par",
}


def transliterate_hindi(text):
    for hindi, english in sorted(COMMON_NEWS_WORDS.items(), key=lambda item: len(item[0]), reverse=True):
        text = text.replace(hindi, english)
    text = text.replace("क्ष", "ksh").replace("त्र", "tr").replace("ज्ञ", "gy")
    result = []
    skip_next_vowel = False

    for index, char in enumerate(text):
        if char in CONSONANTS:
            result.append(CONSONANTS[char])
            next_char = text[index + 1] if index + 1 < len(text) else ""
            if next_char not in VOWEL_SIGNS and next_char != "्":
                result.append("a")
            skip_next_vowel = False
        elif char in VOWEL_SIGNS:
            if not skip_next_vowel:
                result.append(VOWEL_SIGNS[char])
            skip_next_vowel = False
        elif char in INDEPENDENT_VOWELS:
            result.append(INDEPENDENT_VOWELS[char])
        elif char in SPECIAL_SIGNS:
            result.append(SPECIAL_SIGNS[char])
            skip_next_vowel = char == "्"
        else:
            result.append(char)
            skip_next_vowel = False

    return "".join(result)


def seo_slugify(text, max_length=210):
    romanized = transliterate_hindi(text or "")
    slug = slugify(romanized)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:max_length].strip("-")


def unique_article_slug(article_model, title, instance_pk=None):
    base_slug = seo_slugify(title) or f"news-{timezone.now():%Y%m%d}-{uuid.uuid4().hex[:8]}"
    slug = base_slug
    counter = 2
    queryset = article_model.objects.filter(slug=slug)
    if instance_pk:
        queryset = queryset.exclude(pk=instance_pk)
    while queryset.exists():
        suffix = f"-{counter}"
        slug = f"{base_slug[:240 - len(suffix)]}{suffix}"
        counter += 1
        queryset = article_model.objects.filter(slug=slug)
        if instance_pk:
            queryset = queryset.exclude(pk=instance_pk)
    return slug
