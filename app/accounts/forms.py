from pathlib import Path

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
            "avatar",
            "email",
            "affiliation",
            "position",
            "bio",
            "research_interests",
            "orcid",
            "google_scholar_url",
            "github_url",
            "contact_email",
            "public_enabled",
        )
        labels = {
            "display_name": "姓名",
            "avatar": "头像",
            "affiliation": "机构或身份",
            "position": "职位或学术身份",
            "bio": "个人简介",
            "research_interests": "研究方向",
            "orcid": "ORCID",
            "google_scholar_url": "Google Scholar",
            "github_url": "GitHub",
            "contact_email": "公开联系邮箱",
            "public_enabled": "启用公开个人主页",
        }
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 5}),
            "research_interests": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].initial = self.instance.user.email

    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        if not avatar or not hasattr(avatar, "size"):
            return avatar
        if avatar.size > 5 * 1024 * 1024:
            raise forms.ValidationError("头像不能超过 5 MB。")
        if Path(avatar.name).suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
            raise forms.ValidationError("头像仅支持 JPG、PNG、WebP 或 GIF。")
        return avatar

    def save(self, commit=True):
        profile = super().save(commit=False)
        profile.user.email = self.cleaned_data["email"]
        if commit:
            profile.user.save(update_fields=["email"])
            profile.save()
        return profile
