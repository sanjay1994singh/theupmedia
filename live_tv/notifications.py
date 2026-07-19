import json
import logging
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.utils import timezone

from .models import LiveTVChannel, PushDevice


logger = logging.getLogger(__name__)
EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


def _chunks(items, size=100):
    for index in range(0, len(items), size):
        yield items[index:index + size]


def _send_expo_messages(messages):
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    access_token = getattr(settings, "EXPO_PUSH_ACCESS_TOKEN", "")
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    request = Request(
        EXPO_PUSH_URL,
        data=json.dumps(messages).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        logger.warning("Expo push request failed: %s", exc)
        return None


def notify_new_video_ready(channel_id):
    channel = LiveTVChannel.objects.filter(pk=channel_id).first()
    if (
        not channel
        or channel.source_type != LiveTVChannel.SourceType.DIRECT
        or channel.hls_status != LiveTVChannel.HLSStatus.COMPLETED
        or not channel.hls_master_url
        or channel.push_notification_sent_at
    ):
        return 0

    tokens = list(PushDevice.objects.filter(is_active=True).values_list("token", flat=True))
    if not tokens:
        return 0

    sent = 0
    for token_batch in _chunks(tokens):
        messages = [
            {
                "to": token,
                "sound": "default",
                "title": "New video available",
                "body": channel.title,
                "priority": "high",
                "channelId": "new-videos",
                "data": {
                    "type": "new_video",
                    "screen": "live",
                    "channel_id": channel.pk,
                    "slug": channel.slug,
                },
            }
            for token in token_batch
        ]
        result = _send_expo_messages(messages)
        if not result:
            continue
        for token, ticket in zip(token_batch, result.get("data") or []):
            if ticket.get("status") == "ok":
                sent += 1
            elif (ticket.get("details") or {}).get("error") == "DeviceNotRegistered":
                PushDevice.objects.filter(token=token).update(is_active=False)

    if sent:
        LiveTVChannel.objects.filter(
            pk=channel.pk,
            push_notification_sent_at__isnull=True,
        ).update(push_notification_sent_at=timezone.now())
    return sent
