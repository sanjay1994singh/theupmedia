import logging
import threading

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)

EVENTS = {
    "created": {
        "subject": "Welcome to The UP Media",
        "heading": "Welcome to The UP Media",
        "message": "Your account has been created successfully. You can now use the same account across The UP Media services.",
        "accent": "#e31b23",
        "security": False,
    },
    "contact_changed": {
        "subject": "Your The UP Media contact details changed",
        "heading": "Contact details updated",
        "message": "The email address or mobile number linked to your account was changed.",
        "accent": "#e31b23",
        "security": True,
    },
    "password_changed": {
        "subject": "Your The UP Media password changed",
        "heading": "Password changed",
        "message": "Your account password was changed successfully.",
        "accent": "#e31b23",
        "security": True,
    },
    "deletion_scheduled": {
        "subject": "Action required: account deletion scheduled",
        "heading": "Account deletion scheduled",
        "message": "Your account is scheduled for permanent deletion after 48 hours.",
        "accent": "#e31b23",
        "security": True,
    },
    "deletion_cancelled": {
        "subject": "Your account deletion was cancelled",
        "heading": "Deletion cancelled",
        "message": "Your account deletion request has been cancelled and your account remains active.",
        "accent": "#15803d",
        "security": True,
    },
    "deleted": {
        "subject": "Your The UP Media account was deleted",
        "heading": "Account deleted",
        "message": "Your account and linked personal data have been permanently deleted.",
        "accent": "#374151",
        "security": False,
    },
}


def send_account_email(event, email, *, display_name="", details=""):
    if not email:
        return False
    config = EVENTS.get(event)
    if not config:
        logger.error("Unknown account email event: %s", event)
        return False
    context = {
        **config,
        "display_name": display_name or "User",
        "details": details or "",
        "year": timezone.now().year,
        "site_url": getattr(settings, "PUBLIC_SITE_URL", "https://theupmedia.in").rstrip("/"),
        "support_email": getattr(settings, "CONTACT_EMAIL", "srbc500@gmail.com"),
        "support_phone": getattr(settings, "CONTACT_PHONE", "+91 8279408396"),
    }
    html = render_to_string("emails/account_email.html", context)
    text = render_to_string("emails/account_email.txt", context)
    try:
        mail = EmailMultiAlternatives(config["subject"], text, settings.DEFAULT_FROM_EMAIL, [email])
        mail.attach_alternative(html, "text/html")
        mail.send(fail_silently=False)
        return True
    except Exception:
        logger.exception("Account email %s failed for %s", event, email)
        return False


def queue_account_email(event, email, *, display_name="", details=""):
    """Queue email without delaying or failing the user-facing request."""
    if not email or event not in EVENTS:
        return False

    def dispatch():
        try:
            from .tasks import send_account_email_task

            send_account_email_task.apply_async(
                kwargs={
                    "event": event,
                    "email": email,
                    "display_name": display_name,
                    "details": details,
                },
                retry=False,
            )
        except Exception:
            logger.exception("Could not queue account email %s for %s", event, email)

    def start_dispatch():
        threading.Thread(target=dispatch, name=f"account-email-{event}", daemon=True).start()

    transaction.on_commit(start_dispatch)
    return True
