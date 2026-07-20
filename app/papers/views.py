import csv
from io import StringIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_http_methods

from app.research_objects.models import ResearchObject
from app.research_objects.services import visible_objects

from .forms import PaperImportForm, PaperMetadataForm
from .services import import_paper


def _csv_cell(value):
    text = str(value or "")
    return f"'{text}" if text.startswith(("=", "+", "-", "@")) else text


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
            if obj.is_shared_with_team:
                messages.success(request, "文献已导入并加入团队知识库。")
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


@login_required
@require_http_methods(["GET", "POST"])
def metadata_edit(request, pk):
    obj = get_object_or_404(
        ResearchObject.objects.active(),
        pk=pk,
        owner=request.user,
        object_type=ResearchObject.ObjectType.PAPER,
    )
    form = PaperMetadataForm(
        request.POST or None,
        research_object=obj,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "文献题录已由你手动校正。")
        return redirect("research_objects:detail", pk=obj.pk)
    return render(
        request,
        "papers/metadata_form.html",
        {"form": form, "object": obj},
    )


@login_required
@require_GET
def csv_export(request):
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        [
            "title",
            "authors",
            "year",
            "journal",
            "doi",
            "external_url",
            "abstract",
            "personal_note",
            "tags",
            "created_at",
            "updated_at",
        ]
    )
    papers = (
        ResearchObject.objects.active()
        .filter(owner=request.user, object_type=ResearchObject.ObjectType.PAPER)
        .prefetch_related("tags")
        .order_by("pk")
    )
    for paper in papers:
        metadata = paper.metadata_json or {}
        authors = metadata.get("authors", [])
        if not isinstance(authors, list):
            authors = [authors]
        writer.writerow(
            [
                _csv_cell(paper.title),
                _csv_cell("; ".join(str(author) for author in authors)),
                metadata.get("year") or "",
                _csv_cell(metadata.get("journal")),
                _csv_cell(metadata.get("doi")),
                _csv_cell(metadata.get("external_url")),
                _csv_cell(metadata.get("abstract")),
                _csv_cell(paper.content_markdown),
                _csv_cell("; ".join(paper.tags.values_list("name", flat=True))),
                paper.created_at.isoformat(),
                paper.updated_at.isoformat(),
            ]
        )
    response = HttpResponse(
        "\ufeff" + output.getvalue(),
        content_type="text/csv; charset=utf-8",
    )
    response["Content-Disposition"] = 'attachment; filename="papers.csv"'
    return response
