import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from app.comments.forms import CommentForm
from app.accounts.services import StorageQuotaExceeded, reserve_storage
from app.sharing.forms import ObjectShareForm
from app.sharing.services import (
    can_access_attachment,
    can_comment,
    can_edit,
    can_manage,
    object_access_recipients,
)

from .forms import (
    AttachmentForm,
    ImageAttachmentForm,
    ObjectEditConflict,
    ObjectRelationForm,
    ResearchObjectForm,
)
from .models import Attachment, ObjectRelation, ResearchObject
from .services import (
    attachment_image_content_type,
    render_markdown,
    search_objects,
    visible_objects,
)

TEAM_SHARED_DEFAULT_TYPES = {
    ResearchObject.ObjectType.PAPER,
    ResearchObject.ObjectType.WRITING,
    ResearchObject.ObjectType.RESOURCE,
}


def _owned_object_or_404(user, pk):
    return get_object_or_404(
        ResearchObject.objects.active().filter(owner=user),
        pk=pk,
    )


def _visible_object_or_404(user, pk):
    return get_object_or_404(visible_objects(user), pk=pk)


def _visible_attachments(user, obj):
    return [
        attachment
        for attachment in obj.attachments.all()
        if can_access_attachment(user, attachment)
    ]


def _split_image_attachments(attachments):
    images = []
    files = []
    for attachment in attachments:
        content_type = attachment_image_content_type(attachment)
        if content_type:
            attachment.display_content_type = content_type
            images.append(attachment)
        else:
            files.append(attachment)
    return images, files


def _persist_attachment(form, obj, owner):
    upload = form.cleaned_data["file"]
    digest = hashlib.sha256()
    for chunk in upload.chunks():
        digest.update(chunk)
    upload.seek(0)
    attachment = form.save(commit=False)
    attachment.owner = owner
    attachment.research_object = obj
    attachment.original_name = upload.name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    attachment.mime_type = upload.content_type or ""
    attachment.size = upload.size
    attachment.sha256 = digest.hexdigest()
    with transaction.atomic():
        reserve_storage(owner, upload.size)
        attachment.save()
    return attachment


def _image_markdown(attachment):
    alt_text = Path(attachment.original_name).stem
    alt_text = alt_text.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")
    inline_url = reverse("research_objects:attachment_inline", args=[attachment.pk])
    return f"![{alt_text}]({inline_url})"


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
    if object_type not in ResearchObject.ObjectType.values:
        object_type = ResearchObject.ObjectType.NOTE
    templates = {
        ResearchObject.ObjectType.IDEA: "## 想法描述\n\n\n## 相关依据\n\n\n## 下一步验证\n\n",
        ResearchObject.ObjectType.EXPERIMENT: "## 实验目的\n\n\n## 代码与配置\n\n\n## 启动命令\n\n```bash\n\n```\n\n## 结果位置\n\n\n## 关键结果\n\n\n## 结论与下一步\n\n",
        ResearchObject.ObjectType.ISSUE: "## 问题现象\n\n\n## 已尝试方法\n\n\n## 最终解决\n\n\n## 相关命令或链接\n\n",
        ResearchObject.ObjectType.PAPER: "## 一句话笔记\n\n\n## 关键内容\n\n\n## 与当前研究的关系\n\n",
    }
    initial = {
        "object_type": object_type,
        "content_markdown": templates.get(object_type, ""),
        "is_shared_with_team": object_type in TEAM_SHARED_DEFAULT_TYPES,
    }
    form = ResearchObjectForm(
        request.POST or None,
        owner=request.user,
        initial=initial,
    )
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        if obj.is_shared_with_team:
            messages.success(request, "内容已创建，并已加入团队知识库。")
        else:
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
    image_attachments, attachments = _split_image_attachments(
        _visible_attachments(request.user, obj)
    )
    visible_ids = visible_objects(request.user).values_list("pk", flat=True)
    outgoing_relations = obj.outgoing_relations.filter(
        target_object_id__in=visible_ids
    ).select_related("target_object")
    incoming_relations = obj.incoming_relations.filter(
        source_object_id__in=visible_ids
    ).select_related("source_object")
    publication_snapshot = None
    access_recipients = []
    if can_manage(request.user, obj):
        from app.publications.models import PublicationSnapshot

        publication_snapshot = PublicationSnapshot.objects.filter(
            source_object=obj
        ).first()
        access_recipients = object_access_recipients(obj)
    return render(
        request,
        "research_objects/detail.html",
        {
            "object": obj,
            "content_html": render_markdown(obj.content_markdown),
            "attachment_form": AttachmentForm(),
            "attachments": attachments,
            "image_attachments": image_attachments,
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
            "access_recipients": access_recipients,
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
    if request.method == "POST" and form.is_valid():
        try:
            form.save()
        except ObjectEditConflict:
            form.add_error(
                None,
                "此内容已在其他页面更新。你的草稿仍保留在当前页面；请先复制草稿，再决定是否刷新并合并。",
            )
            image_attachments, _ = _split_image_attachments(
                _visible_attachments(request.user, obj)
            )
            return render(
                request,
                "research_objects/form.html",
                {
                    "form": form,
                    "heading": "编辑内容",
                    "object": obj,
                    "can_manage": may_manage,
                    "image_attachments": image_attachments,
                },
                status=409,
            )
        messages.success(request, "内容已保存。")
        return redirect("research_objects:detail", pk=obj.pk)
    image_attachments, _ = _split_image_attachments(
        _visible_attachments(request.user, obj)
    )
    return render(
        request,
        "research_objects/form.html",
        {
            "form": form,
            "heading": "编辑内容",
            "object": obj,
            "can_manage": may_manage,
            "image_attachments": image_attachments,
        },
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
        return JsonResponse(
            {"message": "自动保存失败，请检查必填字段。"},
            status=422,
        )
    try:
        saved = form.save()
    except ObjectEditConflict:
        return JsonResponse(
            {"message": "服务器上存在更新版本，自动保存已暂停。"},
            status=409,
        )
    return JsonResponse(
        {
            "message": "已自动保存",
            "version": saved.version,
        }
    )


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
@require_GET
def workspace_export(request):
    objects = list(
        ResearchObject.objects.active()
        .filter(owner=request.user)
        .select_related("project")
        .prefetch_related("tags", "attachments")
        .order_by("pk")
    )
    manifest = {
        "format": "research-workspace-lite-v1",
        "username": request.user.get_username(),
        "objects": [],
    }
    archive_file = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024)
    with zipfile.ZipFile(
        archive_file,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for obj in objects:
            safe_title = slugify(obj.title, allow_unicode=True)[:80] or "research-object"
            markdown_path = f"objects/{obj.pk}-{safe_title}.md"
            attachment_records = []
            exported_markdown = obj.content_markdown
            for attachment in obj.attachments.all():
                original_name = Path(attachment.original_name).name
                attachment_path = (
                    f"attachments/{obj.pk}/{attachment.pk}-{original_name}"
                )
                exported = False
                if attachment.file.storage.exists(attachment.file.name):
                    with attachment.file.open("rb") as source:
                        with archive.open(attachment_path, "w") as destination:
                            shutil.copyfileobj(source, destination, length=1024 * 1024)
                    exported = True
                    inline_url = reverse(
                        "research_objects:attachment_inline",
                        args=[attachment.pk],
                    )
                    exported_markdown = exported_markdown.replace(
                        inline_url,
                        f"../{attachment_path}",
                    )
                attachment_records.append(
                    {
                        "id": attachment.pk,
                        "name": original_name,
                        "path": attachment_path if exported else None,
                        "size": attachment.size,
                        "sha256": attachment.sha256,
                    }
                )
            archive.writestr(markdown_path, exported_markdown.encode("utf-8"))
            manifest["objects"].append(
                {
                    "id": obj.pk,
                    "type": obj.object_type,
                    "title": obj.title,
                    "markdown_path": markdown_path,
                    "metadata": obj.metadata_json,
                    "project": obj.project.name if obj.project else None,
                    "tags": list(obj.tags.values_list("name", flat=True)),
                    "favorite": obj.is_favorite,
                    "archived": obj.is_archived,
                    "created_at": obj.created_at.isoformat(),
                    "updated_at": obj.updated_at.isoformat(),
                    "attachments": attachment_records,
                }
            )
        archive.writestr(
            "manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
        )
    archive_file.seek(0)
    return FileResponse(
        archive_file,
        as_attachment=True,
        filename=f"research-workspace-{request.user.get_username()}.zip",
        content_type="application/zip",
    )


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
        try:
            _persist_attachment(form, obj, request.user)
        except StorageQuotaExceeded as exc:
            messages.error(request, str(exc))
            return redirect("research_objects:detail", pk=obj.pk)
        messages.success(request, "附件已上传，仍保持私有。")
    else:
        messages.error(request, form.errors.as_text())
    return redirect("research_objects:detail", pk=obj.pk)


@login_required
@require_POST
def image_upload(request, pk):
    obj = _owned_object_or_404(request.user, pk)
    form = ImageAttachmentForm(request.POST, request.FILES)
    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"
    if not form.is_valid():
        error = " ".join(
            message
            for errors in form.errors.values()
            for message in errors
        )
        if is_ajax:
            return JsonResponse({"error": error}, status=422)
        messages.error(request, error)
        return redirect("research_objects:detail", pk=obj.pk)
    try:
        attachment = _persist_attachment(form, obj, request.user)
    except StorageQuotaExceeded as exc:
        if is_ajax:
            return JsonResponse({"error": str(exc)}, status=422)
        messages.error(request, str(exc))
        return redirect("research_objects:detail", pk=obj.pk)

    inline_url = reverse(
        "research_objects:attachment_inline",
        args=[attachment.pk],
    )
    if is_ajax:
        return JsonResponse(
            {
                "id": attachment.pk,
                "name": attachment.original_name,
                "inline_url": inline_url,
                "download_url": reverse(
                    "research_objects:attachment_download",
                    args=[attachment.pk],
                ),
                "markdown": _image_markdown(attachment),
            },
            status=201,
        )
    messages.success(request, "实验图片已上传，可在编辑页插入正文。")
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


@login_required
@require_GET
def attachment_inline(request, pk):
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
    content_type = attachment_image_content_type(attachment)
    if not content_type:
        raise Http404
    response = FileResponse(
        attachment.file.open("rb"),
        as_attachment=False,
        filename=attachment.original_name,
        content_type=content_type,
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
@require_POST
def attachment_delete(request, pk):
    attachment = get_object_or_404(
        Attachment.objects.select_related("research_object"),
        pk=pk,
        owner=request.user,
        research_object__owner=request.user,
        research_object__deleted_at__isnull=True,
    )
    obj = attachment.research_object
    attachment.delete()
    messages.success(request, "附件已删除。")
    if request.POST.get("return_to") == "edit":
        return redirect("research_objects:edit", pk=obj.pk)
    return redirect("research_objects:detail", pk=obj.pk)
