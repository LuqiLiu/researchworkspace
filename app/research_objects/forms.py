from pathlib import Path

from django import forms
from django.db import transaction

from .models import Attachment, ResearchObject, Tag


class ResearchObjectForm(forms.ModelForm):
    tag_names = forms.CharField(
        label="标签",
        required=False,
        help_text="多个标签使用逗号分隔。",
    )

    class Meta:
        model = ResearchObject
        fields = ("object_type", "title", "content_markdown")
        labels = {
            "object_type": "类型",
            "title": "标题",
            "content_markdown": "正文（Markdown）",
        }

    def __init__(self, *args, owner=None, **kwargs):
        self.owner = owner
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["tag_names"].initial = ", ".join(
                self.instance.tags.values_list("name", flat=True)
            )

    @transaction.atomic
    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.owner and not obj.pk:
            obj.owner = self.owner
        if commit:
            obj.save()
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
