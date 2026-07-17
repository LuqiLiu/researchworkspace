from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.db import transaction

from app.audit.models import SecurityAuditLog
from app.audit.services import record_event
from app.projects.models import Project, ProjectMember
from app.publications.models import PublicationSnapshot
from app.research_objects.models import Attachment, ResearchObject, Tag

from .models import UserProfile


class StorageQuotaExceeded(ValidationError):
    pass


@transaction.atomic
def reserve_storage(user, size):
    size = max(int(size or 0), 0)
    profile = UserProfile.objects.select_for_update().get(user=user)
    if profile.storage_used_bytes + size > profile.storage_quota_bytes:
        remaining = profile.storage_remaining_bytes
        raise StorageQuotaExceeded(
            f"存储配额不足：文件需要 {size} 字节，当前仅剩 {remaining} 字节。"
        )
    profile.storage_used_bytes += size
    profile.save(update_fields=["storage_used_bytes"])
    return profile.storage_used_bytes


@transaction.atomic
def release_storage(user_id, size):
    size = max(int(size or 0), 0)
    try:
        profile = UserProfile.objects.select_for_update().get(user_id=user_id)
    except UserProfile.DoesNotExist:
        return 0
    profile.storage_used_bytes = max(profile.storage_used_bytes - size, 0)
    profile.save(update_fields=["storage_used_bytes"])
    return profile.storage_used_bytes


def _available_publication_slug(owner, requested_slug, *, exclude_pk=None):
    base = requested_slug[:210] or "publication"
    candidate = base
    suffix = 2
    queryset = PublicationSnapshot.objects.filter(owner=owner)
    if exclude_pk:
        queryset = queryset.exclude(pk=exclude_pk)
    while queryset.filter(public_slug=candidate).exists():
        suffix_text = f"-{suffix}"
        candidate = f"{base[: 220 - len(suffix_text)]}{suffix_text}"
        suffix += 1
    return candidate


@transaction.atomic
def transfer_user_data(*, source_user, target_user, actor=None):
    """Transfer all user-owned V1 data from a deactivated account."""
    if source_user.pk == target_user.pk:
        raise ValidationError("源账号和目标账号不能相同。")

    User = get_user_model()
    locked_users = {
        user.pk: user
        for user in User.objects.select_for_update()
        .filter(pk__in=[source_user.pk, target_user.pk])
        .order_by("pk")
    }
    if len(locked_users) != 2:
        raise ValidationError("源账号或目标账号不存在。")
    source_user = locked_users[source_user.pk]
    target_user = locked_users[target_user.pk]
    if source_user.is_active:
        raise ValidationError("数据交接前必须先停用源账号。")
    if not target_user.is_active:
        raise ValidationError("目标账号必须处于启用状态。")

    source_profile = UserProfile.objects.select_for_update().get(user=source_user)
    target_profile = UserProfile.objects.select_for_update().get(user=target_user)
    combined_storage = (
        source_profile.storage_used_bytes + target_profile.storage_used_bytes
    )
    if combined_storage > target_profile.storage_quota_bytes:
        raise StorageQuotaExceeded(
            "目标账号存储配额不足，无法接收源账号的文件。"
        )

    counts = {
        "research_objects": ResearchObject.objects.filter(owner=source_user).count(),
        "attachments": Attachment.objects.filter(owner=source_user).count(),
        "projects": Project.objects.filter(owner=source_user).count(),
        "publications": PublicationSnapshot.objects.filter(owner=source_user).count(),
        "tags": Tag.objects.filter(owner=source_user).count(),
    }

    for source_tag in Tag.objects.select_for_update().filter(owner=source_user):
        target_tag, _ = Tag.objects.get_or_create(
            owner=target_user,
            normalized_name=source_tag.normalized_name,
            defaults={"name": source_tag.name},
        )
        for research_object in source_tag.research_objects.all():
            research_object.tags.add(target_tag)
        source_tag.delete()

    source_projects = Project.objects.select_for_update().filter(owner=source_user)
    ProjectMember.objects.filter(
        project__in=source_projects,
        user=target_user,
    ).delete()

    for snapshot in PublicationSnapshot.objects.select_for_update().filter(
        owner=source_user
    ):
        snapshot.public_slug = _available_publication_slug(
            target_user,
            snapshot.public_slug,
            exclude_pk=snapshot.pk,
        )
        snapshot.owner = target_user
        snapshot.save(update_fields=["owner", "public_slug", "updated_at"])

    Attachment.objects.filter(owner=source_user).update(owner=target_user)
    ResearchObject.objects.filter(owner=source_user).update(owner=target_user)
    source_projects.update(owner=target_user)

    target_profile.storage_used_bytes = combined_storage
    target_profile.save(update_fields=["storage_used_bytes"])
    source_profile.storage_used_bytes = 0
    source_profile.public_enabled = False
    source_profile.save(update_fields=["storage_used_bytes", "public_enabled"])

    record_event(
        actor=actor,
        event_type=SecurityAuditLog.EventType.OWNERSHIP_TRANSFERRED,
        resource=source_user,
        target_user=target_user,
        metadata={
            "source_username": source_user.get_username(),
            "target_username": target_user.get_username(),
            **counts,
        },
    )
    return counts
