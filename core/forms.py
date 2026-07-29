from django import forms


class ContactForm(forms.Form):
    name = forms.CharField(max_length=120)
    email = forms.EmailField()
    subject = forms.CharField(max_length=160)
    message = forms.CharField(widget=forms.Textarea, min_length=20)
    website = forms.CharField(required=False, widget=forms.HiddenInput)


class AccountDeletionRequestForm(forms.Form):
    username = forms.CharField(max_length=150, help_text="The UP Media app username")
    email = forms.EmailField(help_text="Account se registered email")
    reason = forms.CharField(required=False, max_length=1000, widget=forms.Textarea)
    website = forms.CharField(required=False, widget=forms.HiddenInput)
