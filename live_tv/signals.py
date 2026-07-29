import logging
import threading

from django.db.models.signals import post_save
from django.dispatch import receiver

from blog.models import BlogPost
from news.models import Article
from services.models import Service

from .notifications import notify_content_update


logger = logging.getLogger(__name__)


def _send(**kwargs):
    def runner():
        try:
            notify_content_update(**kwargs)
        except Exception:
            logger.exception("Content push notification failed")
    threading.Thread(target=runner, name="content-push", daemon=True).start()


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
