from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from app.audit.models import SecurityAuditLog
from app.audit.services import record_event

from .forms import ProjectForm, ProjectMemberForm, ProjectMemberUpdateForm
from .models import Project, ProjectMember


def _visible_project_or_404(user, pk):
    return get_object_or_404(Project.objects.visible_to(user), pk=pk)


def _can_edit_project(user, project):
    if project.owner_id == user.id:
        return True
    return ProjectMember.objects.filter(
        project=project,
        user=user,
        role=ProjectMember.Role.EDITOR,
    ).exists()


@login_required
def project_list(request):
    projects = Project.objects.visible_to(request.user)
    if request.GET.get("archived") != "1":
        projects = projects.filter(is_archived=False)
    return render(request, "projects/list.html", {"projects": projects})


@login_required
@require_http_methods(["GET", "POST"])
def project_create(request):
    form = ProjectForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        project = form.save(commit=False)
        project.owner = request.user
        project.save()
        messages.success(request, "项目已创建。")
        return redirect("projects:detail", pk=project.pk)
    return render(
        request,
        "projects/form.html",
        {"form": form, "heading": "新建项目"},
    )


@login_required
def project_detail(request, pk):
    project = _visible_project_or_404(request.user, pk)
    objects = project.research_objects.filter(deleted_at__isnull=True)
    if project.owner_id != request.user.id:
        objects = objects.filter(is_shared_with_project=True)
    return render(
        request,
        "projects/detail.html",
        {
            "project": project,
            "objects": objects.select_related("owner"),
            "member_form": (
                ProjectMemberForm(project=project)
                if project.owner_id == request.user.id
                else None
            ),
            "can_edit_project": _can_edit_project(request.user, project),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def project_edit(request, pk):
    project = _visible_project_or_404(request.user, pk)
    if not _can_edit_project(request.user, project):
        raise Http404
    form = ProjectForm(request.POST or None, instance=project)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "项目已保存。")
        return redirect("projects:detail", pk=project.pk)
    return render(
        request,
        "projects/form.html",
        {"form": form, "heading": "编辑项目", "project": project},
    )


@login_required
@require_POST
def member_add(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk, owner=request.user)
    form = ProjectMemberForm(request.POST, project=project)
    if form.is_valid():
        membership = form.save(commit=False)
        membership.project = project
        membership.save()
        record_event(
            actor=request.user,
            event_type=SecurityAuditLog.EventType.PROJECT_MEMBER_ADDED,
            resource=project,
            target_user=membership.user,
            metadata={"role": membership.role},
        )
        messages.success(request, "项目成员已添加。")
    else:
        messages.error(request, form.errors.as_text())
    return redirect("projects:detail", pk=project.pk)


@login_required
@require_POST
def member_update(request, pk):
    membership = get_object_or_404(
        ProjectMember.objects.select_related("project", "user"),
        pk=pk,
        project__owner=request.user,
    )
    form = ProjectMemberUpdateForm(request.POST, instance=membership)
    if form.is_valid():
        form.save()
        record_event(
            actor=request.user,
            event_type=SecurityAuditLog.EventType.PROJECT_MEMBER_UPDATED,
            resource=membership.project,
            target_user=membership.user,
            metadata={"role": membership.role},
        )
        messages.success(request, "项目角色已更新。")
    return redirect("projects:detail", pk=membership.project_id)


@login_required
@require_POST
def member_remove(request, pk):
    membership = get_object_or_404(
        ProjectMember.objects.select_related("project", "user"),
        pk=pk,
        project__owner=request.user,
    )
    project = membership.project
    target_user = membership.user
    old_role = membership.role
    membership.delete()
    record_event(
        actor=request.user,
        event_type=SecurityAuditLog.EventType.PROJECT_MEMBER_REMOVED,
        resource=project,
        target_user=target_user,
        metadata={"role": old_role},
    )
    messages.success(request, "项目成员已移除，其项目访问权限立即失效。")
    return redirect("projects:detail", pk=project.pk)
