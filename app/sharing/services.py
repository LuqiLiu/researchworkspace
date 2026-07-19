from django.db.models import Q

from app.projects.models import ProjectMember

from .models import ObjectShare

PERMISSION_RANK = {
    ObjectShare.Permission.VIEWER: 10,
    ObjectShare.Permission.COMMENTER: 20,
    ObjectShare.Permission.EDITOR: 30,
}

PERMISSION_LABEL = {
    10: "查看",
    20: "查看和评论",
    30: "查看、评论和编辑",
}


def object_access_recipients(obj):
    """List effective recipients, merging direct and project access routes."""
    recipients = {}

    def add_recipient(user, rank, source, include_attachments):
        if user.pk == obj.owner_id:
            return
        current = recipients.setdefault(
            user.pk,
            {
                "user": user,
                "rank": 0,
                "sources": [],
                "include_attachments": False,
            },
        )
        current["rank"] = max(current["rank"], rank)
        if source not in current["sources"]:
            current["sources"].append(source)
        current["include_attachments"] = (
            current["include_attachments"] or include_attachments
        )

    for share in obj.direct_shares.all():
        add_recipient(
            share.user,
            PERMISSION_RANK[share.permission],
            "直接分享",
            share.include_attachments,
        )

    if obj.is_shared_with_project and obj.project_id:
        project_source = f"项目：{obj.project.name}"
        add_recipient(
            obj.project.owner,
            30,
            project_source,
            obj.share_project_attachments,
        )
        for membership in obj.project.memberships.all():
            rank = 20
            if membership.role == ProjectMember.Role.EDITOR:
                rank = 30
            add_recipient(
                membership.user,
                rank,
                project_source,
                obj.share_project_attachments,
            )

    result = []
    for recipient in recipients.values():
        recipient["permission_label"] = PERMISSION_LABEL[recipient["rank"]]
        result.append(recipient)
    return sorted(result, key=lambda item: item["user"].get_username().lower())


def visible_objects(user):
    from app.research_objects.models import ResearchObject

    if not user.is_authenticated:
        return ResearchObject.objects.none()
    return (
        ResearchObject.objects.active()
        .filter(
            Q(owner=user)
            | Q(direct_shares__user=user)
            | Q(
                is_shared_with_project=True,
                project__memberships__user=user,
            )
            | Q(is_shared_with_project=True, project__owner=user)
        )
        .select_related("owner", "project")
        .prefetch_related("tags")
        .distinct()
    )


def permission_rank(user, obj):
    if not user.is_authenticated:
        return 0
    if obj.owner_id == user.id:
        return 100

    rank = 0
    direct_permission = (
        ObjectShare.objects.filter(research_object=obj, user=user)
        .values_list("permission", flat=True)
        .first()
    )
    if direct_permission:
        rank = max(rank, PERMISSION_RANK[direct_permission])

    if obj.is_shared_with_project and obj.project_id:
        if obj.project.owner_id == user.id:
            rank = max(rank, 30)
        membership = (
            ProjectMember.objects.filter(project_id=obj.project_id, user=user)
            .values_list("role", flat=True)
            .first()
        )
        if membership == ProjectMember.Role.MEMBER:
            rank = max(rank, 20)
        elif membership == ProjectMember.Role.EDITOR:
            rank = max(rank, 30)
    return rank


def can_view(user, obj):
    return permission_rank(user, obj) >= 10


def can_comment(user, obj):
    return permission_rank(user, obj) >= 20


def can_edit(user, obj):
    return permission_rank(user, obj) >= 30


def can_manage(user, obj):
    return user.is_authenticated and obj.owner_id == user.id


def can_access_attachment(user, attachment):
    obj = attachment.research_object
    if obj.deleted_at is not None:
        return False
    if obj.owner_id == user.id:
        return True
    if ObjectShare.objects.filter(
        research_object=obj,
        user=user,
        include_attachments=True,
    ).exists():
        return True
    if (
        obj.is_shared_with_project
        and obj.share_project_attachments
        and obj.project_id
    ):
        return (
            obj.project.owner_id == user.id
            or ProjectMember.objects.filter(
                project_id=obj.project_id,
                user=user,
            ).exists()
        )
    return False


def sync_object_status(obj):
    from app.research_objects.models import ResearchObject

    is_shared = obj.is_shared_with_project or ObjectShare.objects.filter(
        research_object=obj
    ).exists()
    status = (
        ResearchObject.Status.SHARED
        if is_shared
        else ResearchObject.Status.PRIVATE
    )
    if obj.status != status:
        ResearchObject.objects.filter(pk=obj.pk).update(status=status)
        obj.status = status
