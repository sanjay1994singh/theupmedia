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
            "is_active",
            "is_live",
            "lower_third_label",
            "headline",
            "display_order",
            "meta_title",
            "meta_description",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "meta_description": forms.Textarea(attrs={"rows": 2}),
            "source_type": forms.RadioSelect,
        }
