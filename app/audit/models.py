from django.conf import settings
from django.db import models


class SecurityAuditLog(models.Model):
    class EventType(models.TextChoices):
        SHARE_CREATED = "SHARE_CREATED", "Share created"
        SHARE_UPDATED = "SHARE_UPDATED", "Share updated"
        SHARE_REVOKED = "SHARE_REVOKED", "Share revoked"
        PROJECT_MEMBER_ADDED = "PROJECT_MEMBER_ADDED", "Project member added"
        PROJECT_MEMBER_UPDATED = "PROJECT_MEMBER_UPDATED", "Project member updated"
        PROJECT_MEMBER_REMOVED = "PROJECT_MEMBER_REMOVED", "Project member removed"
        COMMENT_DELETED = "COMMENT_DELETED", "Comment deleted"
        PUBLICATION_PUBLISHED = "PUBLICATION_PUBLISHED", "Publication published"
        PUBLICATION_WITHDRAWN = "PUBLICATION_WITHDRAWN", "Publication withdrawn"
        BACKUP_CREATED = "BACKUP_CREATED", "Backup created"
        RESTORE_COMPLETED = "RESTORE_COMPLETED", "Restore completed"
        OWNERSHIP_TRANSFERRED = (
            "OWNERSHIP_TRANSFERRED",
            "User data ownership transferred",
        )

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="security_events",
    )
    event_type = models.CharField(max_length=40, choices=EventType.choices)
    resource_type = models.CharField(max_length=80)
    resource_id = models.PositiveBigIntegerField()
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="targeted_security_events",
    )
    metadata_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("resource_type", "resource_id", "-created_at")),
        ]

    def __str__(self):
        return f"{self.event_type} {self.resource_type}:{self.resource_id}"
