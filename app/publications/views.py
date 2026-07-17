import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from django.utils.text import slugify

from app.accounts.models import UserProfile
from app.audit.models import SecurityAuditLog
from app.audit.services import record_event
from app.research_objects.models import ResearchObject

from .forms import PublicationSnapshotForm
from .models import PublicationSnapshot, PublishedAttachment
from .services import (
    public_metadata,
    sensitive_findings,
    sync_public_attachments,
    unique_public_slug,
)

IMAGE_CONTENT_TYPES = {
    ".gif": "image/gif",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def _owned_source_or_404(user, pk):
    return get_object_or_404(
        ResearchObject.objects.active().filter(owner=user),
        pk=pk,
    )


def _owned_snapshot_or_404(user, pk):
    return get_object_or_404(
        PublicationSnapshot.objects.select_related("source_object", "owner__profile"),
        pk=pk,
        owner=user,
    )


def _public_profile_or_404(public_slug):
    return get_object_or_404(
        UserProfile.objects.select_related("user"),
        public_slug=public_slug,
        public_enabled=True,
    )


@login_required
@require_GET
def manage_list(request):
    snapshots = PublicationSnapshot.objects.filter(owner=request.user).select_related(
        "source_object"
    )
    return render(request, "publications/manage_list.html", {"snapshots": snapshots})


@login_required
@require_GET
def public_profile_export(request):
    profile = request.user.profile
    snapshots = list(
        PublicationSnapshot.objects.filter(
            owner=request.user,
            is_published=True,
        )
        .prefetch_related("public_attachments")
        .order_by("pk")
    )
    archive_file = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024)
    manifest = {
        "format": "research-workspace-lite-public-v1",
        "profile": {
            "display_name": profile.display_name,
            "affiliation": profile.affiliation,
            "position": profile.position,
            "bio": profile.bio,
            "research_interests": profile.research_interests,
            "orcid": profile.orcid,
            "contact_email": profile.contact_email,
            "public_slug": profile.public_slug,
        },
        "snapshots": [],
    }
    with zipfile.ZipFile(
        archive_file,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for snapshot in snapshots:
            safe_title = slugify(snapshot.title, allow_unicode=True)[:80] or "publication"
            markdown_path = f"publications/{snapshot.pk}-{safe_title}.md"
            archive.writestr(markdown_path, snapshot.content_markdown.encode("utf-8"))
            public_files = []
            for attachment in snapshot.public_attachments.all():
                original_name = Path(attachment.original_name).name
                attachment_path = (
                    f"public-files/{snapshot.pk}/{attachment.pk}-{original_name}"
                )
                exported = False
                if attachment.file.storage.exists(attachment.file.name):
                    with attachment.file.open("rb") as source:
                        with archive.open(attachment_path, "w") as destination:
                            shutil.copyfileobj(source, destination, length=1024 * 1024)
                    exported = True
                public_files.append(
                    {
                        "name": original_name,
                        "path": attachment_path if exported else None,
                        "size": attachment.size,
                        "sha256": attachment.sha256,
                    }
                )
            manifest["snapshots"].append(
                {
                    "title": snapshot.title,
                    "summary": snapshot.summary,
                    "public_slug": snapshot.public_slug,
                    "public_project_name": snapshot.public_project_name,
                    "public_project_summary": snapshot.public_project_summary,
                    "metadata": snapshot.metadata_json,
                    "published_at": (
                        snapshot.published_at.isoformat()
                        if snapshot.published_at
                        else None
                    ),
                    "markdown_path": markdown_path,
                    "attachments": public_files,
                }
            )
        archive.writestr(
            "profile.json",
            json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
        )
    archive_file.seek(0)
    return FileResponse(
        archive_file,
        as_attachment=True,
        filename=f"public-profile-{profile.public_slug or request.user.username}.zip",
        content_type="application/zip",
    )


@login_required
@require_http_methods(["GET", "POST"])
def edit_from_source(request, source_pk):
    source = _owned_source_or_404(request.user, source_pk)
    try:
        snapshot = source.publication_snapshot
    except PublicationSnapshot.DoesNotExist:
        snapshot = PublicationSnapshot(source_object=source, owner=request.user)

    initial = None
    if not snapshot.pk:
        initial = {
            "title": source.title,
            "public_slug": unique_public_slug(request.user, source.title),
            "summary": "",
            "content_markdown": source.content_markdown,
        }
    form = PublicationSnapshotForm(
        request.POST or None,
        request.FILES or None,
        instance=snapshot,
        initial=initial,
        source_object=source,
        owner=request.user,
    )
    if request.method == "POST" and form.is_valid():
        is_new = not snapshot.pk
        snapshot = form.save(commit=False)
        if is_new:
            snapshot.metadata_json = public_metadata(source)
        findings = sensitive_findings(snapshot)
        was_published = snapshot.is_published
        if findings and was_published:
            snapshot.is_published = False
        with transaction.atomic():
            snapshot.save()
            sync_public_attachments(snapshot, form.cleaned_data["public_attachments"])
        if findings and was_published:
            record_event(
                actor=request.user,
                event_type=SecurityAuditLog.EventType.PUBLICATION_WITHDRAWN,
                resource=snapshot,
                metadata={"public_slug": snapshot.public_slug, "reason": "sensitive_edit"},
            )
        if findings:
            messages.warning(
                request,
                ("快照已自动撤下；" if was_published else "草稿已保存，但")
                + "发布前请处理："
                + "、".join(findings)
                + "。",
            )
        elif was_published:
            messages.success(request, "公开快照已安全更新。")
        else:
            messages.success(request, "公开快照草稿已保存。")
        return redirect("publications:preview", pk=snapshot.pk)
    return render(
        request,
        "publications/form.html",
        {"form": form, "source": source, "snapshot": snapshot},
    )


@login_required
@require_GET
def preview(request, pk):
    snapshot = _owned_snapshot_or_404(request.user, pk)
    return render(
        request,
        "publications/detail.html",
        {
            "snapshot": snapshot,
            "profile": snapshot.owner.profile,
            "preview": True,
            "sensitive_findings": sensitive_findings(snapshot),
        },
    )


@login_required
@require_GET
def preview_attachment(request, pk):
    attachment = get_object_or_404(
        PublishedAttachment.objects.select_related("snapshot"),
        pk=pk,
        snapshot__owner=request.user,
    )
    if not attachment.file.storage.exists(attachment.file.name):
        raise Http404
    return FileResponse(
        attachment.file.open("rb"),
        as_attachment=True,
        filename=attachment.original_name,
        content_type=attachment.mime_type or "application/octet-stream",
    )


@login_required
@require_GET
def preview_cover(request, pk):
    snapshot = _owned_snapshot_or_404(request.user, pk)
    suffix = Path(snapshot.cover_image.name).suffix.lower()
    if not snapshot.cover_image or suffix not in IMAGE_CONTENT_TYPES:
        raise Http404
    if not snapshot.cover_image.storage.exists(snapshot.cover_image.name):
        raise Http404
    return FileResponse(snapshot.cover_image.open("rb"), content_type=IMAGE_CONTENT_TYPES[suffix])


@login_required
@require_POST
def publish(request, pk):
    snapshot = _owned_snapshot_or_404(request.user, pk)
    findings = sensitive_findings(snapshot)
    if findings:
        messages.error(
            request,
            "发布已阻止，请先处理：" + "、".join(findings) + "。",
        )
        return redirect("publications:preview", pk=snapshot.pk)
    snapshot.publish()
    record_event(
        actor=request.user,
        event_type=SecurityAuditLog.EventType.PUBLICATION_PUBLISHED,
        resource=snapshot,
        metadata={"public_slug": snapshot.public_slug},
    )
    messages.success(request, "公开快照已发布。")
    return redirect("publications:preview", pk=snapshot.pk)


@login_required
@require_POST
def withdraw(request, pk):
    snapshot = _owned_snapshot_or_404(request.user, pk)
    snapshot.withdraw()
    record_event(
        actor=request.user,
        event_type=SecurityAuditLog.EventType.PUBLICATION_WITHDRAWN,
        resource=snapshot,
        metadata={"public_slug": snapshot.public_slug},
    )
    messages.success(request, "公开快照已撤下，公开地址立即失效。")
    return redirect("publications:preview", pk=snapshot.pk)


@never_cache
@require_GET
def public_profile(request, public_slug):
    profile = _public_profile_or_404(public_slug)
    snapshots = PublicationSnapshot.objects.filter(
        owner=profile.user,
        is_published=True,
    ).select_related("source_object")
    return render(
        request,
        "publications/profile.html",
        {"profile": profile, "snapshots": snapshots[:12]},
    )


@never_cache
@require_GET
def public_publications(request, public_slug):
    profile = _public_profile_or_404(public_slug)
    snapshots = PublicationSnapshot.objects.filter(
        owner=profile.user,
        is_published=True,
        source_object__object_type=ResearchObject.ObjectType.PAPER,
    ).select_related("source_object")
    return render(
        request,
        "publications/publication_list.html",
        {"profile": profile, "snapshots": snapshots},
    )


@never_cache
@require_GET
def public_detail(request, public_slug, snapshot_slug):
    profile = _public_profile_or_404(public_slug)
    snapshot = get_object_or_404(
        PublicationSnapshot.objects.select_related("source_object", "owner__profile"),
        owner=profile.user,
        public_slug=snapshot_slug,
        is_published=True,
    )
    return render(
        request,
        "publications/detail.html",
        {"snapshot": snapshot, "profile": profile, "preview": False},
    )


@never_cache
@require_GET
def public_attachment(request, pk):
    attachment = get_object_or_404(
        PublishedAttachment.objects.select_related("snapshot__owner__profile"),
        pk=pk,
        snapshot__is_published=True,
        snapshot__owner__profile__public_enabled=True,
    )
    if not attachment.file.storage.exists(attachment.file.name):
        raise Http404
    response = FileResponse(
        attachment.file.open("rb"),
        as_attachment=True,
        filename=attachment.original_name,
        content_type=attachment.mime_type or "application/octet-stream",
    )
    response["X-Content-Type-Options"] = "nosniff"
    return response


@never_cache
@require_GET
def snapshot_cover(request, pk):
    snapshot = get_object_or_404(
        PublicationSnapshot.objects.select_related("owner__profile"),
        pk=pk,
        is_published=True,
        owner__profile__public_enabled=True,
    )
    suffix = Path(snapshot.cover_image.name).suffix.lower()
    if not snapshot.cover_image or suffix not in IMAGE_CONTENT_TYPES:
        raise Http404
    if not snapshot.cover_image.storage.exists(snapshot.cover_image.name):
        raise Http404
    return FileResponse(
        snapshot.cover_image.open("rb"),
        content_type=IMAGE_CONTENT_TYPES[suffix],
    )


@never_cache
@require_GET
def profile_avatar(request, public_slug):
    profile = _public_profile_or_404(public_slug)
    suffix = Path(profile.avatar.name).suffix.lower()
    if not profile.avatar or suffix not in IMAGE_CONTENT_TYPES:
        raise Http404
    if not profile.avatar.storage.exists(profile.avatar.name):
        raise Http404
    return FileResponse(profile.avatar.open("rb"), content_type=IMAGE_CONTENT_TYPES[suffix])


@require_GET
def robots_txt(request):
    return HttpResponse(
        "User-agent: *\nAllow: /u/\nDisallow: /\n",
        content_type="text/plain; charset=utf-8",
    )
