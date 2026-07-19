from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from app.audit.models import SecurityAuditLog
from app.audit.services import record_event
from app.research_objects.models import ResearchObject

from .forms import ObjectShareForm, ObjectShareUpdateForm
from .models import ObjectShare
from .services import (
    can_manage,
    object_access_recipients,
    sync_object_status,
    visible_objects,
)


@login_required
def shared_with_me(request):
    objects = visible_objects(request.user).exclude(owner=request.user)
    return render(
        request,
        "sharing/shared_with_me.html",
        {"objects": objects},
    )


@login_required
def sent_shares(request):
    objects = list(
        ResearchObject.objects.active()
        .filter(owner=request.user)
        .filter(
            Q(direct_shares__isnull=False)
            | Q(is_shared_with_project=True, project__isnull=False)
        )
        .select_related("project", "project__owner")
        .prefetch_related(
            "tags",
            "direct_shares__user",
            "project__memberships__user",
        )
        .distinct()
    )
    for obj in objects:
        obj.access_recipients = object_access_recipients(obj)
    return render(
        request,
        "sharing/sent_shares.html",
        {"objects": objects},
    )


@login_required
@require_POST
def share_create(request, object_pk):
    obj = get_object_or_404(
        ResearchObject.objects.active(),
        pk=object_pk,
    )
    if not can_manage(request.user, obj):
        raise Http404
    form = ObjectShareForm(
        request.POST,
        research_object=obj,
    )
    if form.is_valid():
        share = form.save(commit=False)
        share.research_object = obj
        share.created_by = request.user
        share.save()
        sync_object_status(obj)
        record_event(
            actor=request.user,
            event_type=SecurityAuditLog.EventType.SHARE_CREATED,
            resource=obj,
            target_user=share.user,
            metadata={
                "permission": share.permission,
                "include_attachments": share.include_attachments,
            },
        )
        messages.success(request, f"已分享给 {share.user.get_username()}。")
    else:
        messages.error(request, form.errors.as_text())
    return redirect("research_objects:detail", pk=obj.pk)


@login_required
@require_POST
def share_update(request, pk):
    share = get_object_or_404(
        ObjectShare.objects.select_related("research_object", "user"),
        pk=pk,
    )
    if not can_manage(request.user, share.research_object):
        raise Http404
    form = ObjectShareUpdateForm(request.POST, instance=share)
    if form.is_valid():
        form.save()
        record_event(
            actor=request.user,
            event_type=SecurityAuditLog.EventType.SHARE_UPDATED,
            resource=share.research_object,
            target_user=share.user,
            metadata={
                "permission": share.permission,
                "include_attachments": share.include_attachments,
            },
        )
        messages.success(request, "分享权限已更新。")
    else:
        messages.error(request, form.errors.as_text())
    return redirect("research_objects:detail", pk=share.research_object_id)


@login_required
@require_POST
def share_revoke(request, pk):
    share = get_object_or_404(
        ObjectShare.objects.select_related("research_object", "user"),
        pk=pk,
    )
    obj = share.research_object
    if not can_manage(request.user, obj):
        raise Http404
    target_user = share.user
    old_permission = share.permission
    share.delete()
    sync_object_status(obj)
    record_event(
        actor=request.user,
        event_type=SecurityAuditLog.EventType.SHARE_REVOKED,
        resource=obj,
        target_user=target_user,
        metadata={"permission": old_permission},
    )
    messages.success(request, "分享已撤销。")
    return redirect("research_objects:detail", pk=obj.pk)
