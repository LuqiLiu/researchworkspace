import uuid
from pathlib import Path

from django.conf import settings
from django.db import models
from django.utils import timezone


def snapshot_cover_upload_path(instance, filename):
    suffix = Path(filename).suffix.lower()
    return f"publications/{instance.owner_id}/covers/{uuid.uuid4().hex}{suffix}"


def public_attachment_upload_path(instance, filename):
    suffix = Path(filename).suffix.lower()
    return f"publications/{instance.snapshot.owner_id}/files/{uuid.uuid4().hex}{suffix}"


class PublicationSnapshot(models.Model):
    source_object = models.OneToOneField(
        "research_objects.ResearchObject",
        on_delete=models.PROTECT,
        related_name="publication_snapshot",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="publication_snapshots",
    )
    public_slug = models.SlugField(max_length=220, allow_unicode=True)
    title = models.CharField(max_length=240)
    summary = models.TextField(blank=True, max_length=600)
    content_markdown = models.TextField(blank=True)
    content_html = models.TextField(blank=True, editable=False)
    metadata_json = models.JSONField(default=dict, blank=True, editable=False)
    public_project_name = models.CharField(max_length=160, blank=True)
    public_project_summary = models.TextField(blank=True, max_length=600)
    cover_image = models.FileField(upload_to=snapshot_cover_upload_path, blank=True)
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-published_at", "-updated_at")
        constraints = [
            models.UniqueConstraint(
                fields=("owner", "public_slug"),
                name="unique_publication_slug_per_owner",
            )
        ]
        indexes = [
            models.Index(fields=("owner", "is_published", "-published_at")),
        ]

    def save(self, *args, **kwargs):
        from app.research_objects.services import render_markdown

        self.content_html = render_markdown(self.content_markdown)
        super().save(*args, **kwargs)

    def publish(self):
        if not self.published_at:
            self.published_at = timezone.now()
        self.is_published = True
        self.save(update_fields=("is_published", "published_at", "updated_at"))

    def withdraw(self):
        self.is_published = False
        self.save(update_fields=("is_published", "updated_at"))

    def __str__(self):
        return self.title


class PublishedAttachment(models.Model):
    snapshot = models.ForeignKey(
        PublicationSnapshot,
        on_delete=models.CASCADE,
        related_name="public_attachments",
    )
    source_attachment = models.ForeignKey(
        "research_objects.Attachment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="published_copies",
    )
    file = models.FileField(upload_to=public_attachment_upload_path)
    original_name = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=120, blank=True)
    size = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("original_name",)
        constraints = [
            models.UniqueConstraint(
                fields=("snapshot", "source_attachment"),
                name="unique_public_copy_per_source_attachment",
            )
        ]

    def delete(self, *args, **kwargs):
        storage = self.file.storage
        name = self.file.name
        result = super().delete(*args, **kwargs)
        if name and storage.exists(name):
            storage.delete(name)
        return result

    def __str__(self):
        return self.original_name
