from django import forms


class ContactForm(forms.Form):
    name = forms.CharField(max_length=120)
    email = forms.EmailField()
    subject = forms.CharField(max_length=160)
    message = forms.CharField(widget=forms.Textarea, min_length=20)
    website = forms.CharField(required=False, widget=forms.HiddenInput)
