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
            "auto_add_to_live",
            "auto_playlist_enabled",
            "loop_enabled",
            "target_playlist_duration_seconds",
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
        source_type = cleaned_data.get("source_type")
        category = cleaned_data.get("category")
        state = cleaned_data.get("state")
        city = cleaned_data.get("city")
        if source_type != LiveTVChannel.SourceType.PLAYLIST:
            if not category:
                self.add_error("category", "Category is required.")
            if not state:
                self.add_error("state", "State is required.")
            if not city:
                self.add_error("city", "City is required.")
        if state and city and city.state_id != state.pk:
            self.add_error("city", "City must belong to selected state.")
        return cleaned_data
