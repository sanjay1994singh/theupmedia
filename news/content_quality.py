from django.utils.html import strip_tags


MIN_SUMMARY_WORDS = 18
MIN_ARTICLE_WORDS = 300
MIN_META_DESCRIPTION_LENGTH = 80


def article_word_count(article):
    return len(strip_tags(str(article.content or "")).split())


def article_quality_warnings(article):
    warnings = []
    summary_words = len(str(article.summary or "").split())
    body_words = article_word_count(article)

    if summary_words < MIN_SUMMARY_WORDS:
        warnings.append(f"Summary is short ({summary_words} words).")
    if body_words < MIN_ARTICLE_WORDS:
        warnings.append(f"Article body is short ({body_words} words).")
    if not article.featured_image:
        warnings.append("Featured image is missing.")
    if article.featured_image and not article.image_alt_text:
        warnings.append("Featured image alt text is missing.")
    if article.featured_image and not article.image_credit:
        warnings.append("Image credit is missing.")
    if len(article.meta_description or "") < MIN_META_DESCRIPTION_LENGTH:
        warnings.append("Meta description is too short.")
    if not article.source_name and not article.source_url:
        warnings.append("Source/reference details are missing.")
    if not article.reviewed_by_id:
        warnings.append("Reviewed by is not set.")
    if not article.fact_checked_by_id:
        warnings.append("Fact checked by is not set.")
    return warnings
