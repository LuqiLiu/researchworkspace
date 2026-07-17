from pathlib import Path

from django import forms
from django.db import transaction

from app.projects.models import Project

from .models import Attachment, ObjectRelation, ResearchObject, Tag


class ResearchObjectForm(forms.ModelForm):
    tag_names = forms.CharField(
        label="标签",
        required=False,
        help_text="多个标签使用逗号分隔。",
    )

    class Meta:
        model = ResearchObject
        fields = (
            "object_type",
            "title",
            "content_markdown",
            "project",
            "is_shared_with_project",
            "share_project_attachments",
        )
        labels = {
            "object_type": "类型",
            "title": "标题",
            "content_markdown": "正文（Markdown）",
            "project": "关联项目",
            "is_shared_with_project": "项目成员可访问",
            "share_project_attachments": "项目成员也可访问附件",
        }

    def __init__(self, *args, owner=None, can_manage=True, **kwargs):
        self.owner = owner
        self.can_manage = can_manage
        super().__init__(*args, **kwargs)
        self.fields["project"].queryset = Project.objects.visible_to(owner).filter(
            is_archived=False
        )
        if self.instance.pk:
            self.fields["tag_names"].initial = ", ".join(
                self.instance.tags.values_list("name", flat=True)
            )
        if not can_manage:
            for field_name in (
                "tag_names",
                "project",
                "is_shared_with_project",
                "share_project_attachments",
            ):
                self.fields.pop(field_name)

    def clean(self):
        cleaned_data = super().clean()
        if self.can_manage:
            project = cleaned_data.get("project")
            shared = cleaned_data.get("is_shared_with_project")
            share_attachments = cleaned_data.get("share_project_attachments")
            if shared and project is None:
                self.add_error(
                    "is_shared_with_project",
                    "请先选择关联项目。",
                )
            if share_attachments and not shared:
                self.add_error(
                    "share_project_attachments",
                    "必须先允许项目成员访问正文。",
                )
        return cleaned_data

    @transaction.atomic
    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.owner and not obj.pk:
            obj.owner = self.owner
        if commit:
            obj.save()
            if self.can_manage:
                tags = []
                seen = set()
                for raw_name in self.cleaned_data.get("tag_names", "").split(","):
                    name = raw_name.strip()
                    normalized = name.casefold()
                    if not name or normalized in seen:
                        continue
                    seen.add(normalized)
                    tag, _ = Tag.objects.get_or_create(
                        owner=obj.owner,
                        normalized_name=normalized,
                        defaults={"name": name},
                    )
                    tags.append(tag)
                obj.tags.set(tags)
                from app.sharing.services import sync_object_status

                sync_object_status(obj)
        return obj


class AttachmentForm(forms.ModelForm):
    blocked_extensions = {
        ".bat", ".cmd", ".com", ".exe", ".hta", ".js", ".msi", ".ps1",
        ".scr", ".sh", ".vbs",
    }
    max_size = 50 * 1024 * 1024
    blocked_mime_types = {
        "application/x-dosexec",
        "application/x-executable",
        "application/x-msdownload",
        "application/x-sh",
        "text/javascript",
    }

    class Meta:
        model = Attachment
        fields = ("file",)
        labels = {"file": "附件"}

    def clean_file(self):
        upload = self.cleaned_data["file"]
        if upload.size > self.max_size:
            raise forms.ValidationError("单个附件不能超过 50 MB。")
        if Path(upload.name).suffix.lower() in self.blocked_extensions:
            raise forms.ValidationError("不允许上传可执行脚本或程序文件。")
        if (upload.content_type or "").lower() in self.blocked_mime_types:
            raise forms.ValidationError("附件 MIME 类型不安全。")
        return upload


class ObjectRelationForm(forms.ModelForm):
    class Meta:
        model = ObjectRelation
        fields = ("target_object", "relation_type")
        labels = {
            "target_object": "关联目标",
            "relation_type": "关系类型",
        }

    def __init__(self, *args, user=None, source_object=None, **kwargs):
        self.user = user
        self.source_object = source_object
        super().__init__(*args, **kwargs)
        from .services import visible_objects

        self.fields["target_object"].queryset = visible_objects(user).exclude(
            pk=source_object.pk
        )

    def save(self, commit=True):
        relation = super().save(commit=False)
        relation.source_object = self.source_object
        relation.created_by = self.user
        if commit:
            relation.save()
        return relation
