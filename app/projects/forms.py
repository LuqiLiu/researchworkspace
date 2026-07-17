from django import forms
from django.contrib.auth import get_user_model

from .models import Project, ProjectMember


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ("name", "description", "is_archived")
        labels = {
            "name": "项目名称",
            "description": "项目简介",
            "is_archived": "归档项目",
        }


class ProjectMemberForm(forms.ModelForm):
    class Meta:
        model = ProjectMember
        fields = ("user", "role")
        labels = {"user": "成员", "role": "项目角色"}

    def __init__(self, *args, project=None, **kwargs):
        self.project = project
        super().__init__(*args, **kwargs)
        existing_ids = list(
            project.memberships.values_list("user_id", flat=True)
        )
        self.fields["user"].queryset = (
            get_user_model()
            .objects.filter(is_active=True)
            .exclude(pk=project.owner_id)
            .exclude(pk__in=existing_ids)
        )


class ProjectMemberUpdateForm(forms.ModelForm):
    class Meta:
        model = ProjectMember
        fields = ("role",)
        labels = {"role": "项目角色"}
