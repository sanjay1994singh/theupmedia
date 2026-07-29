# Generated for The UP Media mobile UGC moderation controls.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("live_tv", "0052_shortscomment_likes_count_shortscomment_parent_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="BlockedUser",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("blocked_user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="blocked_by_live_tv_users", to=settings.AUTH_USER_MODEL)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="blocked_live_tv_users", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "constraints": [models.UniqueConstraint(fields=("user", "blocked_user"), name="unique_live_tv_blocked_user")],
            },
        ),
        migrations.CreateModel(
            name="ShortsCommentReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reason", models.CharField(blank=True, max_length=500)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("reviewed", "Reviewed"), ("removed", "Content removed")], default="pending", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("comment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reports", to="live_tv.shortscomment")),
                ("reporter", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reported_shorts_comments", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
                "constraints": [models.UniqueConstraint(fields=("comment", "reporter"), name="unique_short_comment_report")],
            },
        ),
    ]
