from django.core.management.base import BaseCommand

from distribution.models import ShareTarget


DEFAULT_TARGETS = [
    ("Mathura WhatsApp News Group", ShareTarget.TargetType.WHATSAPP_GROUP, "Mathura", "", "", True),
    ("UP WhatsApp News Group", ShareTarget.TargetType.WHATSAPP_GROUP, "Uttar Pradesh", "", "", True),
    ("Crime Updates WhatsApp Group", ShareTarget.TargetType.WHATSAPP_GROUP, "Crime", "", "", False),
    ("Politics Updates WhatsApp Group", ShareTarget.TargetType.WHATSAPP_GROUP, "Politics", "", "", False),
    ("The Up Media Telegram Channel", ShareTarget.TargetType.TELEGRAM, "Main", "", "", False),
    ("The Up Media Facebook Page", ShareTarget.TargetType.FACEBOOK, "Main", "", "", False),
]


class Command(BaseCommand):
    help = "Create starter share targets for the distribution panel."

    def handle(self, *args, **options):
        created = 0
        for index, (name, target_type, category, identifier, group_url, default_selected) in enumerate(DEFAULT_TARGETS, start=1):
            _, was_created = ShareTarget.objects.update_or_create(
                name=name,
                defaults={
                    "target_type": target_type,
                    "category": category,
                    "identifier": identifier,
                    "group_url": group_url,
                    "default_selected": default_selected,
                    "is_active": True,
                    "display_order": index,
                },
            )
            created += int(was_created)
        self.stdout.write(self.style.SUCCESS(f"Share targets ready. Created: {created}"))
