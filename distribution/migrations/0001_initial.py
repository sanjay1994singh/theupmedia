import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("news", "0010_article_facebook_post_tracking"),
    ]

    operations = [
        migrations.CreateModel(
            name="ShareCampaign",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=220)),
                ("caption", models.TextField()),
                ("link", models.URLField()),
                ("image_url", models.URLField(blank=True)),
                ("delay_seconds", models.PositiveIntegerField(default=15)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("queued", "Queued"), ("running", "Running"), ("completed", "Completed"), ("failed", "Failed")], default="draft", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("article", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="share_campaigns", to="news.article")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="ShareTarget",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160)),
                ("target_type", models.CharField(choices=[("whatsapp_group", "WhatsApp Group Manual Link"), ("whatsapp_contact", "WhatsApp Business Contact"), ("telegram", "Telegram Channel"), ("facebook", "Facebook Page")], max_length=30)),
                ("category", models.CharField(blank=True, help_text="Mathura, UP, Crime, Politics etc.", max_length=80)),
                ("identifier", models.CharField(blank=True, help_text="Phone number, Telegram chat id, Facebook page id, or internal note.", max_length=220)),
                ("group_url", models.URLField(blank=True, help_text="Optional WhatsApp group invite/link for manual sharing.")),
                ("is_active", models.BooleanField(default=True)),
                ("default_selected", models.BooleanField(default=False)),
                ("display_order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["display_order", "name"],
                "indexes": [
                    models.Index(fields=["target_type", "is_active"], name="dist_target_type_active_idx"),
                    models.Index(fields=["category", "is_active"], name="dist_target_cat_active_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="ShareDelivery",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("pending", "Pending"), ("sent", "Sent"), ("manual", "Manual Share Required"), ("failed", "Failed"), ("skipped", "Skipped")], default="pending", max_length=20)),
                ("manual_share_url", models.URLField(blank=True)),
                ("response", models.TextField(blank=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("campaign", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="deliveries", to="distribution.sharecampaign")),
                ("target", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="deliveries", to="distribution.sharetarget")),
            ],
            options={
                "ordering": ["target__display_order", "target__name"],
                "constraints": [models.UniqueConstraint(fields=("campaign", "target"), name="unique_distribution_delivery")],
            },
        ),
        migrations.AddField(
            model_name="sharecampaign",
            name="targets",
            field=models.ManyToManyField(related_name="campaigns", through="distribution.ShareDelivery", to="distribution.sharetarget"),
        ),
    ]
