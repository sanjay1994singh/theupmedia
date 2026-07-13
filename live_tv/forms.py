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
            "category",
            "state",
            "city",
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

    def clean(self):
        cleaned_data = super().clean()
        state = cleaned_data.get("state")
        city = cleaned_data.get("city")
        if not state:
            self.add_error("state", "State is required.")
        if not city:
            self.add_error("city", "City is required.")
        elif state and city.state_id != state.pk:
            self.add_error("city", "City must belong to selected state.")
        return cleaned_data
