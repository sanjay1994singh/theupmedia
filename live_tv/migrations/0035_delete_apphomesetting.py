from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("live_tv", "0034_socialrenderedvideo_broadcast_session_id_and_more"),
    ]

    operations = [
        migrations.DeleteModel(
            name="AppHomeSetting",
        ),
    ]
