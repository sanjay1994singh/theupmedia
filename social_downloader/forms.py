from django import forms

from .models import SocialMediaDownload
from .services.formats import AUDIO_FORMAT_CHOICES, VIDEO_QUALITY_CHOICES
from .services.validators import validate_public_media_url


class MetadataFetchForm(forms.Form):
    url = forms.URLField(max_length=2000, label="Video URL")

    def clean_url(self):
        url = self.cleaned_data["url"].strip()
        validate_public_media_url(url)
        return url


class DownloadStartForm(forms.Form):
    url = forms.URLField(max_length=2000, label="Video URL")
    download_type = forms.ChoiceField(choices=SocialMediaDownload.DownloadType.choices)
    video_quality = forms.ChoiceField(choices=VIDEO_QUALITY_CHOICES, required=False)
    audio_format = forms.ChoiceField(choices=AUDIO_FORMAT_CHOICES, required=False)

    def clean_url(self):
        url = self.cleaned_data["url"].strip()
        validate_public_media_url(url)
        return url

    def clean(self):
        cleaned = super().clean()
        download_type = cleaned.get("download_type")
        if download_type == SocialMediaDownload.DownloadType.VIDEO and not cleaned.get("video_quality"):
            cleaned["video_quality"] = "best"
        if download_type == SocialMediaDownload.DownloadType.AUDIO and not cleaned.get("audio_format"):
            cleaned["audio_format"] = "mp3"
        return cleaned

