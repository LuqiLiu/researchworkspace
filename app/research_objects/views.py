import hashlib

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .forms import AttachmentForm, ResearchObjectForm
from .models import Attachment, ResearchObject
from .services import render_markdown, search_objects, visible_objects


def _owned_object_or_404(user, pk):
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
    objects = visible_objects(request.user)
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
    initial = {"object_type": request.GET.get("type", ResearchObject.ObjectType.NOTE)}
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
    obj = _owned_object_or_404(request.user, pk)
    return render(
        request,
        "research_objects/detail.html",
        {
            "object": obj,
            "content_html": render_markdown(obj.content_markdown),
            "attachment_form": AttachmentForm(),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def object_edit(request, pk):
    obj = _owned_object_or_404(request.user, pk)
    form = ResearchObjectForm(
        request.POST or None,
        instance=obj,
        owner=request.user,
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
    obj = _owned_object_or_404(request.user, pk)
    form = ResearchObjectForm(request.POST, instance=obj, owner=request.user)
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
    obj = _owned_object_or_404(request.user, pk)
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
        Attachment.objects.select_related("research_object"),
        pk=pk,
        owner=request.user,
        research_object__deleted_at__isnull=True,
    )
    if not attachment.file.storage.exists(attachment.file.name):
        raise Http404
    return FileResponse(
        attachment.file.open("rb"),
        as_attachment=True,
        filename=attachment.original_name,
    )
