import logging
import threading

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from blog.models import BlogPost
from news.models import Article
from services.models import Service

from .notifications import notify_content_update
from .account_emails import queue_account_email


logger = logging.getLogger(__name__)
User = get_user_model()


def _send(**kwargs):
    def runner():
        try:
            notify_content_update(**kwargs)
        except Exception:
            logger.exception("Content push notification failed")
    threading.Thread(target=runner, name="content-push", daemon=True).start()


def _send_account(event, instance, *, email=None, details=""):
    queue_account_email(
        event,
        email if email is not None else instance.email,
        display_name=instance.get_full_name() or instance.get_username(),
        details=details,
    )


@receiver(pre_save, sender=User)
def capture_user_account_changes(sender, instance, **kwargs):
    instance._account_contact_changes = []
    instance._account_previous_email = ""
    instance._account_password_changed = False
    if not instance.pk:
        return
    previous = sender.objects.filter(pk=instance.pk).only("email", "phone_number", "password").first()
    if not previous:
        return
    instance._account_previous_email = previous.email
    if previous.email != instance.email:
        instance._account_contact_changes.append("Email address")
    if getattr(previous, "phone_number", "") != getattr(instance, "phone_number", ""):
        instance._account_contact_changes.append("Mobile number")
    instance._account_password_changed = previous.password != instance.password


@receiver(post_save, sender=User)
def user_account_email(sender, instance, created, **kwargs):
    if not instance.email:
        return
    if created:
        _send_account("created", instance)
        return
    contact_changes = getattr(instance, "_account_contact_changes", [])
    if contact_changes:
        details = "Changed: " + ", ".join(contact_changes)
        recipients = {instance.email, getattr(instance, "_account_previous_email", "")}
        for recipient in filter(None, recipients):
            _send_account("contact_changed", instance, email=recipient, details=details)
    if getattr(instance, "_account_password_changed", False):
        _send_account("password_changed", instance)


@receiver(post_save, sender=Article)
def article_notification(sender, instance, created, **kwargs):
    if instance.status != Article.Status.PUBLISHED:
        return
    _send(content_type="article", title="नई खबर" if created else "खबर अपडेट हुई", body=instance.title, data={"slug": instance.slug})


@receiver(post_save, sender=BlogPost)
def blog_notification(sender, instance, created, **kwargs):
    if instance.status != BlogPost.Status.PUBLISHED:
        return
    _send(content_type="blog", title="नया Blog" if created else "Blog अपडेट हुआ", body=instance.title, data={"url": instance.get_absolute_url()})


@receiver(post_save, sender=Service)
def service_notification(sender, instance, created, **kwargs):
    if not instance.is_active:
        return
    _send(content_type="service", title="नई Service" if created else "Service अपडेट हुई", body=instance.name_hi or instance.name, data={"url": instance.get_absolute_url()})
