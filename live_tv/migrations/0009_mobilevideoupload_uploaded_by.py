from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("live_tv", "0008_socialrenderedvideo_render_format_db_default"),
    ]

    operations = [
        migrations.AddField(
            model_name="mobilevideoupload",
            name="uploaded_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="mobile_video_uploads",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
