from pathlib import Path
from textwrap import wrap

from django.conf import settings
from django.core.files import File
from PIL import Image, ImageDraw, ImageFont


def _font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
        "/usr/share/fonts/truetype/lohit-devanagari/Lohit-Devanagari.ttf",
        "/usr/share/fonts/truetype/deva/lohit_devanagari.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/NirmalaB.ttf" if bold else "C:/Windows/Fonts/Nirmala.ttf",
        "C:/Windows/Fonts/mangal.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def limited_title_lines(title, max_chars=70):
    clean = " ".join(str(title or "").split())
    if len(clean) > max_chars:
        clean = clean[: max_chars - 1].rstrip() + "..."
    return wrap(clean, width=26, break_long_words=False)[:3] or ["THE UP MEDIA"]


def attach_text_thumbnail(article, folder="generated", prefix="article"):
    thumb_dir = Path(settings.MEDIA_ROOT) / "articles" / folder
    thumb_dir.mkdir(parents=True, exist_ok=True)
    file_path = thumb_dir / f"{prefix}-{article.pk}-thumb.jpg"

    image = Image.new("RGB", (1200, 675), "#090909")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 1200, 675), fill="#090909")
    draw.rectangle((0, 0, 1200, 160), fill="#9f1714")
    draw.rectangle((0, 0, 1200, 70), fill="#160404")
    draw.rectangle((38, 190, 1162, 620), outline="#ef2a23", width=10)
    draw.rectangle((52, 204, 1148, 606), outline="#ffffff", width=3)

    draw.text((70, 32), "THE UP MEDIA", fill="#ffffff", font=_font(40, bold=True))
    category = getattr(article.category, "name", "NEWS") or "NEWS"
    draw.rectangle((54, 532, 1146, 606), fill="#df251d")
    draw.text((76, 550), category.upper()[:28], fill="#ffffff", font=_font(34, bold=True))

    y = 235
    for line in limited_title_lines(article.title):
        draw.text((78, y), line, fill="#ffffff", font=_font(50, bold=True), stroke_width=2, stroke_fill="#111111")
        y += 62

    image.save(file_path, "JPEG", quality=90, optimize=True)
    with file_path.open("rb") as image_file:
        article.featured_image.save(file_path.name, File(image_file), save=True)
