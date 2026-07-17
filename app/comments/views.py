from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from app.audit.models import SecurityAuditLog
from app.audit.services import record_event
from app.research_objects.services import visible_objects
from app.sharing.services import can_comment, can_manage, can_view

from .forms import CommentForm
from .models import Comment


@login_required
@require_POST
def comment_create(request, object_pk):
    obj = get_object_or_404(visible_objects(request.user), pk=object_pk)
    if not can_comment(request.user, obj):
        raise Http404
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.research_object = obj
        comment.author = request.user
        parent_id = request.POST.get("parent")
        if parent_id:
            comment.parent = get_object_or_404(
                Comment,
                pk=parent_id,
                research_object=obj,
                deleted_at__isnull=True,
            )
        comment.save()
        messages.success(request, "评论已添加。")
    else:
        messages.error(request, form.errors.as_text())
    return redirect("research_objects:detail", pk=obj.pk)


@login_required
@require_POST
def comment_delete(request, pk):
    comment = get_object_or_404(
        Comment.objects.select_related(
            "research_object",
            "research_object__project",
        ),
        pk=pk,
        deleted_at__isnull=True,
    )
    if not can_view(request.user, comment.research_object):
        raise Http404
    if (
        comment.author_id != request.user.id
        and not can_manage(request.user, comment.research_object)
    ):
        raise Http404
    comment.deleted_at = timezone.now()
    comment.save(update_fields=["deleted_at", "updated_at"])
    record_event(
        actor=request.user,
        event_type=SecurityAuditLog.EventType.COMMENT_DELETED,
        resource=comment.research_object,
        target_user=comment.author,
        metadata={"comment_id": comment.pk},
    )
    messages.success(request, "评论已删除。")
    return redirect("research_objects:detail", pk=comment.research_object_id)
