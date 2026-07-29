import logging
from html import escape

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

logger = logging.getLogger(__name__)

EVENTS = {
    "created": ("Welcome to The UP Media", "Your account has been created successfully."),
    "profile_updated": ("The UP Media profile updated", "Your profile details were updated successfully."),
    "password_changed": ("The UP Media password changed", "Your account password was changed successfully."),
    "deletion_scheduled": ("The UP Media account deletion scheduled", "Your account is scheduled for permanent deletion after 48 hours."),
    "deleted": ("The UP Media account deleted", "Your account and linked personal data have been permanently deleted."),
}


def send_account_email(event, email, *, display_name="", details=""):
    if not email:
        return False
    subject, message = EVENTS[event]
    safe_name = escape(display_name or "User")
    safe_message = escape(message)
    safe_details = escape(details or "").replace("\n", "<br>")
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:620px;margin:auto;border:1px solid #ddd">
      <div style="background:#080808;color:#fff;padding:20px;text-align:center">
        <strong style="font-size:24px">THE <span style="background:#e31b23;padding:5px">UP</span> MEDIA</strong>
      </div>
      <div style="padding:24px;color:#202020">
        <p>Hello {safe_name},</p><p>{safe_message}</p>
        {f"<p>{safe_details}</p>" if safe_details else ""}
        <p>If you did not request this change, contact us immediately.</p>
        <p><a href="https://theupmedia.in/privacy-policy/">Privacy Policy</a> ·
        <a href="https://theupmedia.in/account-deletion/">Account Deletion</a></p>
        <p>Email: srbc500@gmail.com · Phone: +91 8279408396</p>
      </div>
    </div>
    """
    text = f"Hello {display_name or 'User'},\n\n{message}\n{details}\n\nSupport: srbc500@gmail.com | +91 8279408396"
    try:
        mail = EmailMultiAlternatives(subject, text, settings.DEFAULT_FROM_EMAIL, [email])
        mail.attach_alternative(html, "text/html")
        mail.send(fail_silently=False)
        return True
    except Exception:
        logger.exception("Account email %s failed for %s", event, email)
        return False
