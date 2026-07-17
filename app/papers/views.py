from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_http_methods

from app.research_objects.models import ResearchObject
from app.research_objects.services import visible_objects

from .forms import PaperImportForm
from .services import import_paper


@login_required
@require_http_methods(["GET", "POST"])
def paper_import(request):
    form = PaperImportForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        obj, duplicates, remote_loaded = import_paper(
            owner=request.user,
            cleaned_data=form.cleaned_data,
        )
        if duplicates:
            duplicate_titles = "、".join(item.title for item in duplicates[:3])
            messages.warning(
                request,
                f"已保存为个人副本；检测到可能重复的文献：{duplicate_titles}",
            )
        elif obj.metadata_json.get("doi") and not remote_loaded:
            messages.warning(
                request,
                "文献已保存，但外部题录服务暂不可用；你可以稍后手动完善信息。",
            )
        else:
            messages.success(request, "文献已导入并保持私有。")
        return redirect("research_objects:detail", pk=obj.pk)
    return render(request, "papers/import.html", {"form": form})


@login_required
@require_GET
def bibtex_export(request, pk):
    obj = get_object_or_404(
        visible_objects(request.user),
        pk=pk,
        object_type=ResearchObject.ObjectType.PAPER,
    )
    bibtex = obj.metadata_json.get("bibtex", "")
    response = HttpResponse(
        bibtex,
        content_type="application/x-bibtex; charset=utf-8",
    )
    filename = slugify(obj.title)[:80] or f"paper-{obj.pk}"
    response["Content-Disposition"] = f'attachment; filename="{filename}.bib"'
    return response
