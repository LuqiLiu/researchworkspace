import hashlib

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from app.comments.forms import CommentForm
from app.sharing.forms import ObjectShareForm
from app.sharing.services import (
    can_access_attachment,
    can_comment,
    can_edit,
    can_manage,
)

from .forms import AttachmentForm, ObjectRelationForm, ResearchObjectForm
from .models import Attachment, ObjectRelation, ResearchObject
from .services import render_markdown, search_objects, visible_objects


def _owned_object_or_404(user, pk):
    return get_object_or_404(
        ResearchObject.objects.active().filter(owner=user),
        pk=pk,
    )


def _visible_object_or_404(user, pk):
    return get_object_or_404(visible_objects(user), pk=pk)


def _enable_autosave(form, obj):
    autosave_url = reverse("research_objects:autosave", args=[obj.pk])
    attributes = {
        "hx-post": autosave_url,
        "hx-trigger": "keyup changed delay:1200ms",
        "hx-include": "closest form",
        "hx-target": "#autosave-status",
        "hx-swap": "innerHTML",
    }
    form.fields["title"].widget.attrs.update(attributes)
    form.fields["content_markdown"].widget.attrs.update(attributes)


@login_required
def object_list(request):
    objects = visible_objects(request.user).filter(owner=request.user)
    if request.GET.get("archived") != "1":
        objects = objects.filter(is_archived=False)
    if request.GET.get("favorite") == "1":
        objects = objects.filter(is_favorite=True)
    object_type = request.GET.get("type")
    if object_type in ResearchObject.ObjectType.values:
        objects = objects.filter(object_type=object_type)
    return render(
        request,
        "research_objects/list.html",
        {"objects": objects, "object_types": ResearchObject.ObjectType.choices},
    )


@login_required
@require_http_methods(["GET", "POST"])
def object_create(request):
    object_type = request.GET.get("type", ResearchObject.ObjectType.NOTE)
    templates = {
        ResearchObject.ObjectType.IDEA: "## 想法描述\n\n\n## 相关依据\n\n\n## 下一步验证\n\n",
        ResearchObject.ObjectType.EXPERIMENT: "## 实验目的\n\n\n## 代码与配置\n\n\n## 启动命令\n\n```bash\n\n```\n\n## 结果位置\n\n\n## 关键结果\n\n\n## 结论与下一步\n\n",
        ResearchObject.ObjectType.ISSUE: "## 问题现象\n\n\n## 已尝试方法\n\n\n## 最终解决\n\n\n## 相关命令或链接\n\n",
        ResearchObject.ObjectType.PAPER: "## 一句话笔记\n\n\n## 关键内容\n\n\n## 与当前研究的关系\n\n",
    }
    initial = {
        "object_type": object_type,
        "content_markdown": templates.get(object_type, ""),
    }
    form = ResearchObjectForm(
        request.POST or None,
        owner=request.user,
        initial=initial,
    )
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        messages.success(request, "内容已创建，当前仅你自己可见。")
        return redirect("research_objects:detail", pk=obj.pk)
    return render(
        request,
        "research_objects/form.html",
        {"form": form, "heading": "新建内容"},
    )


@login_required
def object_detail(request, pk):
    obj = _visible_object_or_404(request.user, pk)
    comments = obj.comments.filter(deleted_at__isnull=True).select_related(
        "author", "parent"
    )
    attachments = [
        attachment
        for attachment in obj.attachments.all()
        if can_access_attachment(request.user, attachment)
    ]
    visible_ids = visible_objects(request.user).values_list("pk", flat=True)
    outgoing_relations = obj.outgoing_relations.filter(
        target_object_id__in=visible_ids
    ).select_related("target_object")
    incoming_relations = obj.incoming_relations.filter(
        source_object_id__in=visible_ids
    ).select_related("source_object")
    publication_snapshot = None
    if can_manage(request.user, obj):
        from app.publications.models import PublicationSnapshot

        publication_snapshot = PublicationSnapshot.objects.filter(
            source_object=obj
        ).first()
    return render(
        request,
        "research_objects/detail.html",
        {
            "object": obj,
            "content_html": render_markdown(obj.content_markdown),
            "attachment_form": AttachmentForm(),
            "attachments": attachments,
            "comment_form": CommentForm(),
            "comments": comments,
            "can_comment": can_comment(request.user, obj),
            "can_edit": can_edit(request.user, obj),
            "can_manage": can_manage(request.user, obj),
            "share_form": (
                ObjectShareForm(research_object=obj)
                if can_manage(request.user, obj)
                else None
            ),
            "relation_form": (
                ObjectRelationForm(user=request.user, source_object=obj)
                if can_manage(request.user, obj)
                else None
            ),
            "outgoing_relations": outgoing_relations,
            "incoming_relations": incoming_relations,
            "publication_snapshot": publication_snapshot,
        },
    )


@login_required
@require_POST
def relation_create(request, pk):
    obj = _owned_object_or_404(request.user, pk)
    form = ObjectRelationForm(
        request.POST,
        user=request.user,
        source_object=obj,
    )
    if form.is_valid():
        form.save()
        messages.success(request, "关联关系已建立。")
    else:
        messages.error(request, form.errors.as_text())
    return redirect("research_objects:detail", pk=obj.pk)


@login_required
@require_POST
def relation_delete(request, pk):
    relation = get_object_or_404(
        ObjectRelation.objects.select_related("source_object"),
        pk=pk,
        source_object__owner=request.user,
        source_object__deleted_at__isnull=True,
    )
    source_id = relation.source_object_id
    relation.delete()
    messages.success(request, "关联关系已移除。")
    return redirect("research_objects:detail", pk=source_id)


@login_required
@require_http_methods(["GET", "POST"])
def object_edit(request, pk):
    obj = _visible_object_or_404(request.user, pk)
    if not can_edit(request.user, obj):
        raise Http404
    may_manage = can_manage(request.user, obj)
    form = ResearchObjectForm(
        request.POST or None,
        instance=obj,
        owner=obj.owner,
        can_manage=may_manage,
    )
    _enable_autosave(form, obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "内容已保存。")
        return redirect("research_objects:detail", pk=obj.pk)
    return render(
        request,
        "research_objects/form.html",
        {"form": form, "heading": "编辑内容", "object": obj},
    )


@login_required
@require_POST
def object_autosave(request, pk):
    obj = _visible_object_or_404(request.user, pk)
    if not can_edit(request.user, obj):
        raise Http404
    form = ResearchObjectForm(
        request.POST,
        instance=obj,
        owner=obj.owner,
        can_manage=can_manage(request.user, obj),
    )
    if not form.is_valid():
        return HttpResponse("自动保存失败，请检查必填字段。", status=422)
    form.save()
    return HttpResponse("已自动保存")


@login_required
@require_POST
def object_toggle(request, pk, field):
    obj = _owned_object_or_404(request.user, pk)
    if field not in {"is_favorite", "is_archived"}:
        raise Http404
    setattr(obj, field, not getattr(obj, field))
    obj.save(update_fields=[field, "updated_at"])
    return redirect("research_objects:detail", pk=obj.pk)


@login_required
@require_POST
def object_delete(request, pk):
    obj = _owned_object_or_404(request.user, pk)
    obj.soft_delete()
    messages.success(request, "内容已移入回收状态。")
    return redirect("research_objects:list")


@login_required
@require_GET
def object_export(request, pk):
    obj = _visible_object_or_404(request.user, pk)
    safe_title = slugify(obj.title)[:80] or "research-object"
    response = HttpResponse(
        obj.content_markdown,
        content_type="text/markdown; charset=utf-8",
    )
    response["Content-Disposition"] = (
        f'attachment; filename="{obj.pk}-{safe_title}.md"'
    )
    return response


@login_required
def search(request):
    query = request.GET.get("q", "")
    return render(
        request,
        "research_objects/search.html",
        {"query": query, "objects": search_objects(request.user, query)},
    )


@login_required
@require_POST
def attachment_upload(request, pk):
    obj = _owned_object_or_404(request.user, pk)
    form = AttachmentForm(request.POST, request.FILES)
    if form.is_valid():
        upload = request.FILES["file"]
        digest = hashlib.sha256()
        for chunk in upload.chunks():
            digest.update(chunk)
        upload.seek(0)
        attachment = form.save(commit=False)
        attachment.owner = request.user
        attachment.research_object = obj
        attachment.original_name = upload.name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        attachment.mime_type = upload.content_type or ""
        attachment.size = upload.size
        attachment.sha256 = digest.hexdigest()
        attachment.save()
        messages.success(request, "附件已上传，仍保持私有。")
    else:
        messages.error(request, form.errors.as_text())
    return redirect("research_objects:detail", pk=obj.pk)


@login_required
@require_GET
def attachment_download(request, pk):
    attachment = get_object_or_404(
        Attachment.objects.select_related(
            "research_object",
            "research_object__project",
        ),
        pk=pk,
        research_object__deleted_at__isnull=True,
    )
    if not can_access_attachment(request.user, attachment):
        raise Http404
    if not attachment.file.storage.exists(attachment.file.name):
        raise Http404
    return FileResponse(
        attachment.file.open("rb"),
        as_attachment=True,
        filename=attachment.original_name,
    )
