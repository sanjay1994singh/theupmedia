from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("live_tv", "0026_livetvcity_alter_livetvchannel_city_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="ShortsComment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(blank=True, max_length=80)),
                ("text", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("short", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="comments", to="live_tv.shortsvideo")),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="shortscomment",
            index=models.Index(fields=["short", "-created_at"], name="short_comment_recent_idx"),
        ),
    ]
