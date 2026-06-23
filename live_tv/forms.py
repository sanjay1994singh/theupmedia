from django import forms

from .models import LiveTVChannel


class LiveTVChannelForm(forms.ModelForm):
    class Meta:
        model = LiveTVChannel
        fields = [
            "title",
            "slug",
            "description",
            "source_type",
            "youtube_url",
            "stream_url",
            "video_file",
            "poster_image",
            "channel_logo",
            "is_active",
            "is_live",
            "autoplay",
            "show_lower_third",
            "lower_third_label",
            "headline",
            "show_ticker",
            "ticker_label",
            "ticker_text",
            "show_channel_logo",
            "display_order",
            "meta_title",
            "meta_description",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "ticker_text": forms.Textarea(attrs={"rows": 3}),
            "meta_description": forms.Textarea(attrs={"rows": 2}),
            "source_type": forms.RadioSelect,
        }
