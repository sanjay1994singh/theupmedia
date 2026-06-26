from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("news", "0009_fetchednews_fact_points_fetchednews_internal_note_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="article",
            name="facebook_post_id",
            field=models.CharField(blank=True, editable=False, max_length=120),
        ),
        migrations.AddField(
            model_name="article",
            name="facebook_posted_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="article",
            name="facebook_post_error",
            field=models.TextField(blank=True, editable=False),
        ),
    ]
