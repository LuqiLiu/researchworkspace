import uuid
from pathlib import Path

from django.conf import settings
from django.db import models
from django.utils import timezone


class OwnedObjectQuerySet(models.QuerySet):
    def active(self):
        return self.filter(deleted_at__isnull=True)

    def visible_to(self, user):
        if not user.is_authenticated:
            return self.none()
        return self.active().filter(owner=user)


class Tag(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="research_tags",
    )
    name = models.CharField(max_length=80)
    normalized_name = models.CharField(max_length=80, editable=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("owner", "normalized_name"),
                name="unique_tag_per_owner",
            )
        ]
        ordering = ("name",)

    def save(self, *args, **kwargs):
        self.name = self.name.strip()
        self.normalized_name = self.name.casefold()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ResearchObject(models.Model):
    class ObjectType(models.TextChoices):
        NOTE = "NOTE", "普通笔记"
        PAPER = "PAPER", "文献"
        IDEA = "IDEA", "科研想法"
        EXPERIMENT = "EXPERIMENT", "实验记录"
        ISSUE = "ISSUE", "问题与踩坑"
        WRITING = "WRITING", "写作素材"
        RESOURCE = "RESOURCE", "资源索引"

    class Status(models.TextChoices):
        PRIVATE = "PRIVATE", "仅自己"
        SHARED = "SHARED", "已分享"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="research_objects",
    )
    object_type = models.CharField(
        max_length=20,
        choices=ObjectType.choices,
        default=ObjectType.NOTE,
    )
    title = models.CharField(max_length=240)
    content_markdown = models.TextField()
    content_plain_text = models.TextField(blank=True, editable=False)
    metadata_json = models.JSONField(default=dict, blank=True)
    search_text = models.TextField(blank=True, editable=False)
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="research_objects",
    )
    is_shared_with_project = models.BooleanField(default=False)
    share_project_attachments = models.BooleanField(default=False)
    is_shared_with_team = models.BooleanField(default=False)
    share_team_attachments = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PRIVATE,
        editable=False,
    )
    tags = models.ManyToManyField(
        Tag,
        blank=True,
        related_name="research_objects",
    )
    is_favorite = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    version = models.PositiveBigIntegerField(default=1, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = OwnedObjectQuerySet.as_manager()

    class Meta:
        ordering = ("-updated_at",)
        indexes = [
            models.Index(fields=("owner", "deleted_at", "-updated_at")),
            models.Index(fields=("owner", "is_archived")),
        ]

    def save(self, *args, **kwargs):
        from .services import markdown_to_plain_text
        from .services import compose_search_text

        if not self.project_id:
            self.is_shared_with_project = False
            self.share_project_attachments = False
        if not self.is_shared_with_project:
            self.share_project_attachments = False
        elif self.project_id:
            self.status = self.Status.SHARED
        if not self.is_shared_with_team:
            self.share_team_attachments = False
        else:
            self.status = self.Status.SHARED
        self.content_plain_text = markdown_to_plain_text(self.content_markdown)
        self.search_text = compose_search_text(self)
        super().save(*args, **kwargs)

    def soft_delete(self):
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at", "updated_at"])

    def __str__(self):
        return self.title


def attachment_upload_path(instance, filename):
    suffix = Path(filename).suffix.lower()
    return f"attachments/{instance.owner_id}/{uuid.uuid4().hex}{suffix}"


class Attachment(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    research_object = models.ForeignKey(
        ResearchObject,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField(upload_to=attachment_upload_path)
    original_name = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=120, blank=True)
    size = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.original_name


class ObjectRelation(models.Model):
    class RelationType(models.TextChoices):
        RELATED = "RELATED", "关联"
        DERIVED_FROM = "DERIVED_FROM", "来源于"
        CITES = "CITES", "引用"
        SUPPORTS = "SUPPORTS", "支持"
        CONTRADICTS = "CONTRADICTS", "反驳"
        VALIDATES = "VALIDATES", "验证"
        USES = "USES", "使用"
        PRODUCES = "PRODUCES", "产生"
        BELONGS_TO = "BELONGS_TO", "属于"
        FOLLOW_UP = "FOLLOW_UP", "后续工作"

    source_object = models.ForeignKey(
        ResearchObject,
        on_delete=models.CASCADE,
        related_name="outgoing_relations",
    )
    target_object = models.ForeignKey(
        ResearchObject,
        on_delete=models.CASCADE,
        related_name="incoming_relations",
    )
    relation_type = models.CharField(
        max_length=30,
        choices=RelationType.choices,
        default=RelationType.RELATED,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_object_relations",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("source_object", "target_object", "relation_type"),
                name="unique_typed_object_relation",
            ),
            models.CheckConstraint(
                condition=~models.Q(source_object=models.F("target_object")),
                name="relation_objects_must_differ",
            ),
        ]
        ordering = ("relation_type", "target_object__title")

    def __str__(self):
        return f"{self.source_object} {self.relation_type} {self.target_object}"
