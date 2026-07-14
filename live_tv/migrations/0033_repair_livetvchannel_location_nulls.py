from django.db import migrations


def repair_location_nulls(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("ALTER TABLE live_tv_livetvchannel MODIFY category_id bigint NULL")
        cursor.execute("ALTER TABLE live_tv_livetvchannel MODIFY state_id bigint NULL")
        cursor.execute("ALTER TABLE live_tv_livetvchannel MODIFY city_id bigint NULL")


class Migration(migrations.Migration):
    dependencies = [
        ("live_tv", "0032_auto_live_playlist"),
    ]

    operations = [
        migrations.RunPython(repair_location_nulls, migrations.RunPython.noop),
    ]
