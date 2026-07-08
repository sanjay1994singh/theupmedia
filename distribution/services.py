import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.utils import timezone

from .models import ShareCampaign, ShareDelivery, ShareTarget


TIMEOUT = int(os.getenv("SOCIAL_POST_TIMEOUT", "30"))


def post_json(url, payload, headers=None):
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    with urlopen(request, timeout=TIMEOUT) as response:
        return response.status, response.read().decode("utf-8", errors="ignore")


def send_telegram(delivery):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = delivery.target.identifier or os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return False, "TELEGRAM_BOT_TOKEN or chat id missing"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": delivery.campaign.share_text,
        "disable_web_page_preview": False,
    }
    status, body = post_json(url, payload)
    return 200 <= status < 300, body[:500]


def send_facebook(delivery):
    page_id = delivery.target.identifier or os.getenv("FACEBOOK_PAGE_ID", "")
    token = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN", "")
    graph_version = os.getenv("FACEBOOK_GRAPH_API_VERSION", "v20.0")
    if not page_id or not token:
        return False, "FACEBOOK_PAGE_ID/target identifier or FACEBOOK_PAGE_ACCESS_TOKEN missing"
    url = f"https://graph.facebook.com/{graph_version}/{page_id}/feed?access_token={token}"
    payload = {"message": delivery.campaign.caption, "link": delivery.campaign.link}
    status, body = post_json(url, payload)
    return 200 <= status < 300, body[:500]


def send_whatsapp_contact(delivery):
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    token = os.getenv("WHATSAPP_BUSINESS_TOKEN", "")
    recipient = delivery.target.identifier
    if not phone_number_id or not token or not recipient:
        return False, "WhatsApp Business phone id/token or recipient missing"
    url = f"https://graph.facebook.com/v20.0/{phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient,
        "type": "text",
        "text": {"body": delivery.campaign.share_text},
    }
    status, body = post_json(url, payload, headers={"Authorization": f"Bearer {token}"})
    return 200 <= status < 300, body[:500]


def run_campaign(campaign):
    campaign.status = ShareCampaign.Status.RUNNING
    campaign.started_at = timezone.now()
    campaign.save(update_fields=["status", "started_at", "updated_at"])

    deliveries = campaign.deliveries.select_related("target").filter(status=ShareDelivery.Status.PENDING)
    failed = 0
    for index, delivery in enumerate(deliveries):
        target_type = delivery.target.target_type
        try:
            if target_type == ShareTarget.TargetType.WHATSAPP_GROUP:
                delivery.mark_manual()
                continue
            if target_type == ShareTarget.TargetType.TELEGRAM:
                ok, response = send_telegram(delivery)
            elif target_type == ShareTarget.TargetType.FACEBOOK:
                ok, response = send_facebook(delivery)
            elif target_type == ShareTarget.TargetType.WHATSAPP_CONTACT:
                ok, response = send_whatsapp_contact(delivery)
            else:
                ok, response = False, "Unsupported target type"

            delivery.status = ShareDelivery.Status.SENT if ok else ShareDelivery.Status.FAILED
            delivery.response = response
            delivery.sent_at = timezone.now()
            delivery.save(update_fields=["status", "response", "sent_at"])
            failed += int(not ok)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            delivery.status = ShareDelivery.Status.FAILED
            delivery.response = str(exc)
            delivery.sent_at = timezone.now()
            delivery.save(update_fields=["status", "response", "sent_at"])
            failed += 1

        if index < deliveries.count() - 1:
            time.sleep(max(0, campaign.delay_seconds))

    campaign.status = ShareCampaign.Status.FAILED if failed else ShareCampaign.Status.COMPLETED
    campaign.completed_at = timezone.now()
    campaign.save(update_fields=["status", "completed_at", "updated_at"])
    return campaign
