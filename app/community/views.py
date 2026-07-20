from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render

from app.projects.models import Project
from app.research_objects.models import ResearchObject, Tag


@login_required
def team_library(request):
    shared_objects = ResearchObject.objects.active().filter(
        is_shared_with_team=True,
        is_archived=False,
    )
    objects = shared_objects.select_related(
        "owner",
        "owner__profile",
        "project",
    ).prefetch_related("tags")

    query = request.GET.get("q", "").strip()
    if query:
        objects = objects.filter(
            Q(title__icontains=query)
            | Q(search_text__icontains=query)
            | Q(tags__name__icontains=query)
            | Q(project__name__icontains=query)
            | Q(
                comments__content__icontains=query,
                comments__deleted_at__isnull=True,
            )
        )

    object_type = request.GET.get("type", "")
    if object_type in ResearchObject.ObjectType.values:
        objects = objects.filter(object_type=object_type)

    project_id = request.GET.get("project", "")
    if project_id.isdigit():
        objects = objects.filter(project_id=int(project_id))

    author_id = request.GET.get("author", "")
    if author_id.isdigit():
        objects = objects.filter(owner_id=int(author_id))

    tag_name = request.GET.get("tag", "").strip()
    if tag_name:
        objects = objects.filter(tags__name__iexact=tag_name)

    objects = objects.distinct().order_by("-updated_at")
    page = Paginator(objects, 24).get_page(request.GET.get("page"))

    projects = Project.objects.filter(
        research_objects__in=shared_objects,
    ).distinct().order_by("name")
    authors = (
        get_user_model()
        .objects.filter(
            is_active=True,
            research_objects__in=shared_objects,
        )
        .select_related("profile")
        .distinct()
        .order_by("username")
    )
    tags = (
        Tag.objects.filter(research_objects__in=shared_objects)
        .values_list("name", flat=True)
        .distinct()
        .order_by("name")
    )
    query_without_page = request.GET.copy()
    query_without_page.pop("page", None)

    return render(
        request,
        "community/library.html",
        {
            "page": page,
            "object_types": ResearchObject.ObjectType.choices,
            "projects": projects,
            "authors": authors,
            "tags": tags,
            "query_without_page": query_without_page.urlencode(),
        },
    )
