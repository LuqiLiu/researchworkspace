from django import forms
from django.contrib.auth import get_user_model

from .models import ObjectShare


class ObjectShareForm(forms.ModelForm):
    class Meta:
        model = ObjectShare
        fields = ("user", "permission", "include_attachments")
        labels = {
            "user": "成员",
            "permission": "权限",
            "include_attachments": "同时允许访问附件",
        }

    def __init__(self, *args, research_object=None, **kwargs):
        self.research_object = research_object
        super().__init__(*args, **kwargs)
        queryset = get_user_model().objects.filter(is_active=True).exclude(
            pk=research_object.owner_id
        )
        existing_user_ids = list(
            research_object.direct_shares.values_list("user_id", flat=True)
        )
        self.fields["user"].queryset = queryset.exclude(pk__in=existing_user_ids)


class ObjectShareUpdateForm(forms.ModelForm):
    class Meta:
        model = ObjectShare
        fields = ("permission", "include_attachments")
        labels = {
            "permission": "权限",
            "include_attachments": "同时允许访问附件",
        }
