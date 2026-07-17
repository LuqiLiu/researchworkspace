from django.conf import settings
from django.db import models


class ObjectShare(models.Model):
    class Permission(models.TextChoices):
        VIEWER = "VIEWER", "查看"
        COMMENTER = "COMMENTER", "查看和评论"
        EDITOR = "EDITOR", "查看、评论和编辑"

    research_object = models.ForeignKey(
        "research_objects.ResearchObject",
        on_delete=models.CASCADE,
        related_name="direct_shares",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_object_shares",
    )
    permission = models.CharField(max_length=20, choices=Permission.choices)
    include_attachments = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_object_shares",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("research_object", "user"),
                name="unique_object_share_user",
            )
        ]
        ordering = ("user__username",)

    def __str__(self):
        return f"{self.research_object} -> {self.user} ({self.permission})"
