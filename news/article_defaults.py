from django.contrib.auth import get_user_model
from django.db import IntegrityError, OperationalError
from django.db.models import Q

from news.models import Category, City, State
from news.slug_utils import seo_slugify


DEFAULT_AUTHOR_NAME = "Charan Singh"


def get_default_author():
    User = get_user_model()
    first = "Charan"
    last = "Singh"
    candidates = [
        Q(first_name__iexact=first, last_name__iexact=last),
        Q(username__iexact="charan") | Q(username__icontains="charan"),
        Q(email__icontains="charan"),
    ]
    for query in candidates:
        author = User.objects.filter(query).order_by("id").first()
        if author:
            return author
    return User.objects.filter(is_superuser=True).order_by("id").first()


def infer_taxonomy(title):
    text = str(title or "").lower()
    rules = [
        (("irfan", "jantar", "protest", "rahul", "worker", "मोहम्मद", "इरफान", "जंतर", "मंतर", "आंदोलन"), "Politics", "Delhi", "Delhi"),
        (("paper leak", "exam", "student", "education", "शिक्षा", "पेपर", "परीक्षा", "छात्र"), "Education", "Delhi", "Delhi"),
        (("e20", "ethanol", "petrol", "fuel", "इथेनॉल", "पेट्रोल"), "Auto", "Delhi", "Delhi"),
        (("vrindavan", "mathura", "वृंदावन", "मथुरा"), "Crime", "Uttar Pradesh", "Mathura"),
        (("weather", "monsoon", "rain", "mausam", "मौसम", "बारिश", "मानसून"), "Weather", "Uttar Pradesh", "Mathura"),
        (("hospital", "health", "doctor", "अस्पताल", "स्वास्थ्य"), "Health", "Uttar Pradesh", "Mathura"),
    ]
    for needles, category, state, city in rules:
        if any(needle in text for needle in needles):
            return category, state, city
    return None, None, None


def get_or_make_category(name):
    if not name:
        return None
    existing = Category.objects.filter(name__iexact=name).first()
    if existing:
        return existing
    try:
        return Category.objects.create(name=name, slug=seo_slugify(name), is_active=True)
    except (IntegrityError, OperationalError):
        return Category.objects.filter(name__iexact=name).first()


def get_or_make_location(state_name, city_name):
    if not state_name:
        return None, None
    state = State.objects.filter(name__iexact=state_name).first()
    if not state:
        try:
            state = State.objects.create(name=state_name, slug=seo_slugify(state_name), is_active=True)
        except (IntegrityError, OperationalError):
            state = State.objects.filter(name__iexact=state_name).first()
    if not state or not city_name:
        return state, None
    city = City.objects.filter(state=state, name__iexact=city_name).first()
    if not city:
        try:
            city = City.objects.create(state=state, name=city_name, slug=seo_slugify(city_name), is_active=True)
        except (IntegrityError, OperationalError):
            city = City.objects.filter(state=state, name__iexact=city_name).first()
    return state, city
