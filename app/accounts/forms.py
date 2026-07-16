from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm

from .models import UserProfile


class EmailOrUsernameAuthenticationForm(AuthenticationForm):
    username = forms.CharField(label="用户名或邮箱")
    password = forms.CharField(label="密码", strip=False, widget=forms.PasswordInput)

    def clean(self):
        identifier = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")
        if identifier and password:
            self.user_cache = authenticate(
                self.request,
                username=identifier,
                password=password,
            )
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            self.confirm_login_allowed(self.user_cache)
        return self.cleaned_data


class UserProfileForm(forms.ModelForm):
    email = forms.EmailField(label="邮箱", required=False)

    class Meta:
        model = UserProfile
        fields = (
            "display_name",
            "email",
            "affiliation",
            "bio",
            "research_interests",
            "orcid",
        )
        labels = {
            "display_name": "姓名",
            "affiliation": "机构或身份",
            "bio": "个人简介",
            "research_interests": "研究方向",
            "orcid": "ORCID",
        }
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 5}),
            "research_interests": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].initial = self.instance.user.email

    def save(self, commit=True):
        profile = super().save(commit=False)
        profile.user.email = self.cleaned_data["email"]
        if commit:
            profile.user.save(update_fields=["email"])
            profile.save()
        return profile
