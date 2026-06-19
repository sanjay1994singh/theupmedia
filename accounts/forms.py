from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import User


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name", "password1", "password2")


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "email",
            "avatar",
            "cover_image",
            "bio",
            "phone_number",
            "alternate_phone",
            "date_of_birth",
            "gender",
            "designation",
            "organization",
            "address_line_1",
            "address_line_2",
            "city",
            "state",
            "country",
            "postal_code",
            "language",
            "timezone",
            "website",
            "facebook",
            "twitter",
            "instagram",
            "linkedin",
            "youtube",
            "newsletter_subscribed",
        )
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
        }
