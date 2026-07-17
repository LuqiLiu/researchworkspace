from pathlib import Path

from django import forms
from django.core.exceptions import ValidationError
from django.utils.text import slugify

from app.research_objects.models import Attachment

from .models import PublicationSnapshot
from .services import attachment_is_publishable, unique_public_slug


class PublicationSnapshotForm(forms.ModelForm):
    public_attachments = forms.ModelMultipleChoiceField(
        label="允许公开下载的附件",
        queryset=Attachment.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="不会直接公开私人附件；勾选后系统创建独立公开副本。",
    )
    confirm_attachment_rights = forms.BooleanField(
        label="我确认有权公开所选附件",
        required=False,
    )

    class Meta:
        model = PublicationSnapshot
        fields = (
            "title",
            "public_slug",
            "summary",
            "content_markdown",
            "public_project_name",
            "public_project_summary",
            "cover_image",
        )
        labels = {
            "title": "公开标题",
            "public_slug": "公开网址标识",
            "summary": "公开摘要",
            "content_markdown": "公开正文（Markdown）",
            "public_project_name": "公开项目名称",
            "public_project_summary": "公开项目简介",
            "cover_image": "封面图片",
        }
        widgets = {
            "summary": forms.Textarea(attrs={"rows": 4}),
            "public_project_summary": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, source_object, owner, **kwargs):
        self.source_object = source_object
        self.owner = owner
        super().__init__(*args, **kwargs)
        candidates = source_object.attachments.filter(owner=owner)
        self.fields["public_attachments"].queryset = candidates
        if self.instance.pk:
            self.fields["public_attachments"].initial = self.instance.public_attachments.values_list(
                "source_attachment_id", flat=True
            )
        elif not self.initial.get("public_slug"):
            self.initial["public_slug"] = unique_public_slug(owner, source_object.title)

    def clean_public_slug(self):
        value = slugify(self.cleaned_data["public_slug"], allow_unicode=True)
        if not value:
            raise ValidationError("公开网址标识不能为空。")
        queryset = PublicationSnapshot.objects.filter(owner=self.owner, public_slug=value)
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise ValidationError("该公开网址标识已被使用。")
        return value

    def clean_cover_image(self):
        cover = self.cleaned_data.get("cover_image")
        if not cover or not hasattr(cover, "size"):
            return cover
        if cover.size > 8 * 1024 * 1024:
            raise ValidationError("封面图片不能超过 8 MB。")
        if Path(cover.name).suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
            raise ValidationError("封面仅支持 JPG、PNG、WebP 或 GIF。")
        return cover

    def clean(self):
        cleaned_data = super().clean()
        attachments = cleaned_data.get("public_attachments")
        if attachments:
            invalid = [item.original_name for item in attachments if not attachment_is_publishable(item)]
            if invalid:
                self.add_error(
                    "public_attachments",
                    f"以下附件类型不允许公开或文件已丢失：{', '.join(invalid)}",
                )
            if not cleaned_data.get("confirm_attachment_rights"):
                self.add_error("confirm_attachment_rights", "公开附件前必须确认发布权利。")
        return cleaned_data

    def save(self, commit=True):
        snapshot = super().save(commit=False)
        snapshot.source_object = self.source_object
        snapshot.owner = self.owner
        if commit:
            snapshot.save()
        return snapshot
