from django import forms

from news.models import Article

from .models import ShareCampaign, ShareDelivery, ShareTarget


class ShareCampaignForm(forms.ModelForm):
    targets = forms.ModelMultipleChoiceField(
        queryset=ShareTarget.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        required=True,
    )

    class Meta:
        model = ShareCampaign
        fields = ("article", "title", "caption", "link", "image_url", "delay_seconds", "targets")
        widgets = {
            "caption": forms.Textarea(attrs={"rows": 4}),
            "delay_seconds": forms.NumberInput(attrs={"min": 0, "max": 120}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["article"].queryset = Article.published.all()
        self.fields["targets"].queryset = ShareTarget.objects.filter(is_active=True)

    def save(self, commit=True):
        targets = self.cleaned_data.get("targets")
        campaign = super().save(commit=commit)
        if commit:
            campaign.deliveries.exclude(target__in=targets).delete()
            for target in targets:
                ShareDelivery.objects.get_or_create(campaign=campaign, target=target)
        return campaign
