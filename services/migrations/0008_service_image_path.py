from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("services", "0007_add_media_solution_services"),
    ]

    operations = [
        migrations.AddField(
            model_name="service",
            name="image_path",
            field=models.CharField(blank=True, help_text="Static image path, example: img/services/seo/service.svg", max_length=220),
        ),
    ]
