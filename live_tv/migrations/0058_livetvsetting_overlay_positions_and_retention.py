from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("live_tv", "0057_livetvsetting_location_sizes"),
    ]

    operations = [
        migrations.AddField(model_name="livetvsetting", name="web_channel_logo_left_percent", field=models.PositiveSmallIntegerField(blank=True, help_text="Web logo left offset percent. Leave blank to use right.", null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])),
        migrations.AddField(model_name="livetvsetting", name="web_channel_logo_right_percent", field=models.PositiveSmallIntegerField(default=4, help_text="Web logo right offset percent.", validators=[MinValueValidator(0), MaxValueValidator(100)])),
        migrations.AddField(model_name="livetvsetting", name="web_channel_logo_top_percent", field=models.PositiveSmallIntegerField(default=4, help_text="Web logo top offset percent.", validators=[MinValueValidator(0), MaxValueValidator(100)])),
        migrations.AddField(model_name="livetvsetting", name="web_channel_logo_bottom_percent", field=models.PositiveSmallIntegerField(blank=True, help_text="Web logo bottom offset percent. Leave blank to use top.", null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])),
        migrations.AddField(model_name="livetvsetting", name="mobile_channel_logo_left_percent", field=models.PositiveSmallIntegerField(blank=True, help_text="Mobile logo left offset percent. Leave blank to use right.", null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])),
        migrations.AddField(model_name="livetvsetting", name="mobile_channel_logo_right_percent", field=models.PositiveSmallIntegerField(default=4, help_text="Mobile logo right offset percent.", validators=[MinValueValidator(0), MaxValueValidator(100)])),
        migrations.AddField(model_name="livetvsetting", name="mobile_channel_logo_top_percent", field=models.PositiveSmallIntegerField(default=4, help_text="Mobile logo top offset percent.", validators=[MinValueValidator(0), MaxValueValidator(100)])),
        migrations.AddField(model_name="livetvsetting", name="mobile_channel_logo_bottom_percent", field=models.PositiveSmallIntegerField(blank=True, help_text="Mobile logo bottom offset percent. Leave blank to use top.", null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])),
        migrations.AddField(model_name="livetvsetting", name="render_channel_logo_left_percent", field=models.PositiveSmallIntegerField(blank=True, help_text="Rendered video logo left offset percent. Leave blank to use right.", null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])),
        migrations.AddField(model_name="livetvsetting", name="render_channel_logo_right_percent", field=models.PositiveSmallIntegerField(default=2, help_text="Rendered video logo right offset percent.", validators=[MinValueValidator(0), MaxValueValidator(100)])),
        migrations.AddField(model_name="livetvsetting", name="render_channel_logo_top_percent", field=models.PositiveSmallIntegerField(default=4, help_text="Rendered video logo top offset percent.", validators=[MinValueValidator(0), MaxValueValidator(100)])),
        migrations.AddField(model_name="livetvsetting", name="render_channel_logo_bottom_percent", field=models.PositiveSmallIntegerField(blank=True, help_text="Rendered video logo bottom offset percent. Leave blank to use top.", null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])),
        migrations.AddField(model_name="livetvsetting", name="web_live_location_left_percent", field=models.PositiveSmallIntegerField(default=3, help_text="Web location left offset percent.", validators=[MinValueValidator(0), MaxValueValidator(100)])),
        migrations.AddField(model_name="livetvsetting", name="web_live_location_right_percent", field=models.PositiveSmallIntegerField(blank=True, help_text="Web location right offset percent. Leave blank to use left.", null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])),
        migrations.AddField(model_name="livetvsetting", name="web_live_location_top_percent", field=models.PositiveSmallIntegerField(default=4, help_text="Web location top offset percent.", validators=[MinValueValidator(0), MaxValueValidator(100)])),
        migrations.AddField(model_name="livetvsetting", name="web_live_location_bottom_percent", field=models.PositiveSmallIntegerField(blank=True, help_text="Web location bottom offset percent. Leave blank to use top.", null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])),
        migrations.AddField(model_name="livetvsetting", name="mobile_live_location_left_percent", field=models.PositiveSmallIntegerField(default=4, help_text="Mobile location left offset percent.", validators=[MinValueValidator(0), MaxValueValidator(100)])),
        migrations.AddField(model_name="livetvsetting", name="mobile_live_location_right_percent", field=models.PositiveSmallIntegerField(blank=True, help_text="Mobile location right offset percent. Leave blank to use left.", null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])),
        migrations.AddField(model_name="livetvsetting", name="mobile_live_location_top_percent", field=models.PositiveSmallIntegerField(default=5, help_text="Mobile location top offset percent.", validators=[MinValueValidator(0), MaxValueValidator(100)])),
        migrations.AddField(model_name="livetvsetting", name="mobile_live_location_bottom_percent", field=models.PositiveSmallIntegerField(blank=True, help_text="Mobile location bottom offset percent. Leave blank to use top.", null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])),
        migrations.AddField(model_name="livetvsetting", name="render_location_left_percent", field=models.PositiveSmallIntegerField(default=2, help_text="Rendered video location left offset percent.", validators=[MinValueValidator(0), MaxValueValidator(100)])),
        migrations.AddField(model_name="livetvsetting", name="render_location_right_percent", field=models.PositiveSmallIntegerField(blank=True, help_text="Rendered video location right offset percent. Leave blank to use left.", null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])),
        migrations.AddField(model_name="livetvsetting", name="render_location_top_percent", field=models.PositiveSmallIntegerField(default=4, help_text="Rendered video location top offset percent.", validators=[MinValueValidator(0), MaxValueValidator(100)])),
        migrations.AddField(model_name="livetvsetting", name="render_location_bottom_percent", field=models.PositiveSmallIntegerField(blank=True, help_text="Rendered video location bottom offset percent. Leave blank to use top.", null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])),
        migrations.AddField(model_name="livetvsetting", name="live_video_retention_hours", field=models.PositiveIntegerField(default=48, help_text="Uploaded Live TV/video source cleanup retention in hours (1-720). Rendered outputs are preserved.", validators=[MinValueValidator(1), MaxValueValidator(720)])),
    ]
