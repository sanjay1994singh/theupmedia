import json
import logging
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.utils import timezone


logger = logging.getLogger(__name__)
TIMEOUT = int(os.getenv("SOCIAL_POST_TIMEOUT", "30"))


def absolute_article_url(article):
    return f"{settings.SITE_DOMAIN}{article.get_absolute_url()}"


def is_public_article(article):
    return article.status == article.Status.PUBLISHED and article.published_at <= timezone.now()


def _post_json(url, payload, headers=None):
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    with urlopen(request, timeout=TIMEOUT) as response:
        return response.status, response.read().decode("utf-8", errors="ignore")


def notify_telegram(article):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return {"provider": "telegram", "sent": False, "reason": "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing"}
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": f"{article.title}\n{absolute_article_url(article)}",
        "disable_web_page_preview": False,
    }
    try:
        status, body = _post_json(url, payload)
        return {"provider": "telegram", "sent": 200 <= status < 300, "response": body[:300]}
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        logger.warning("Telegram share failed for article %s: %s", article.pk, exc)
        return {"provider": "telegram", "sent": False, "reason": str(exc)}


def notify_facebook_page(article):
    if article.facebook_post_id:
        return {"provider": "facebook_page", "sent": False, "skipped": True, "reason": "already posted"}
    if not is_public_article(article):
        return {"provider": "facebook_page", "sent": False, "reason": "article is not public yet"}

    page_id = os.getenv("FACEBOOK_PAGE_ID", "")
    token = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN", "")
    if not page_id or not token:
        return {"provider": "facebook_page", "sent": False, "reason": "FACEBOOK_PAGE_ID or FACEBOOK_PAGE_ACCESS_TOKEN missing"}
    graph_version = os.getenv("FACEBOOK_GRAPH_API_VERSION", "v20.0")
    query = urlencode({"access_token": token})
    url = f"https://graph.facebook.com/{graph_version}/{page_id}/feed?{query}"
    payload = {
        "message": f"{article.title}\n\n{article.summary[:220]}",
        "link": absolute_article_url(article),
    }
    try:
        status, body = _post_json(url, payload)
        sent = 200 <= status < 300
        response = json.loads(body or "{}")
        if sent:
            article.facebook_post_id = response.get("id", "")
            article.facebook_posted_at = timezone.now()
            article.facebook_post_error = ""
            article.save(update_fields=["facebook_post_id", "facebook_posted_at", "facebook_post_error", "updated_at"])
        else:
            article.facebook_post_error = body[:1000]
            article.save(update_fields=["facebook_post_error", "updated_at"])
        return {"provider": "facebook_page", "sent": sent, "post_id": response.get("id", ""), "response": body[:300]}
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        logger.warning("Facebook page share failed for article %s: %s", article.pk, exc)
        article.facebook_post_error = str(exc)
        article.save(update_fields=["facebook_post_error", "updated_at"])
        return {"provider": "facebook_page", "sent": False, "reason": str(exc)}


def notify_whatsapp_business(article):
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    token = os.getenv("WHATSAPP_BUSINESS_TOKEN", "")
    recipient = os.getenv("WHATSAPP_SHARE_TO", "")
    if not phone_number_id or not token or not recipient:
        return {"provider": "whatsapp_business", "sent": False, "reason": "WhatsApp Business env values missing"}
    url = f"https://graph.facebook.com/v20.0/{phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient,
        "type": "text",
        "text": {"body": f"{article.title}\n{absolute_article_url(article)}"},
    }
    try:
        status, body = _post_json(url, payload, headers={"Authorization": f"Bearer {token}"})
        return {"provider": "whatsapp_business", "sent": 200 <= status < 300, "response": body[:300]}
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        logger.warning("WhatsApp Business share failed for article %s: %s", article.pk, exc)
        return {"provider": "whatsapp_business", "sent": False, "reason": str(exc)}


def run_publish_hooks(article):
    return [
        notify_telegram(article),
        notify_facebook_page(article),
        notify_whatsapp_business(article),
    ]
