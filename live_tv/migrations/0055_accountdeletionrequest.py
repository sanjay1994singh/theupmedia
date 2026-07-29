from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("live_tv", "0054_mobileapprelease")]

    operations = [
        migrations.CreateModel(
            name="AccountDeletionRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("user_id_snapshot", models.PositiveBigIntegerField(db_index=True)),
                ("username_snapshot", models.CharField(blank=True, max_length=150)),
                ("full_name_snapshot", models.CharField(blank=True, max_length=300)),
                ("email_snapshot", models.EmailField(blank=True, max_length=254)),
                ("requested_at", models.DateTimeField(auto_now_add=True)),
                ("scheduled_for", models.DateTimeField(db_index=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("completed", "Completed"), ("failed", "Failed")], db_index=True, default="pending", max_length=16)),
                ("last_error", models.TextField(blank=True)),
            ],
            options={"ordering": ["-requested_at"]},
        ),
    ]
