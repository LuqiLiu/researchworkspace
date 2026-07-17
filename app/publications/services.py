import re
from pathlib import Path

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils.text import slugify

from .models import PublicationSnapshot, PublishedAttachment

PUBLIC_METADATA_FIELDS = (
    "authors",
    "year",
    "journal",
    "doi",
    "external_url",
    "abstract",
)
PUBLIC_ATTACHMENT_EXTENSIONS = {
    ".csv", ".gif", ".jpeg", ".jpg", ".pdf", ".png", ".txt", ".webp", ".zip",
}
SENSITIVE_PATTERNS = (
    ("私钥内容", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.I)),
    (
        "疑似密钥、令牌或密码",
        re.compile(r"\b(?:api[_-]?key|secret|token|password|passwd)\s*[:=]\s*[^\s]+", re.I),
    ),
    (
        "服务器或本机绝对路径",
        re.compile(r"(?:\b[A-Za-z]:\\|/(?:home|srv|var/lib|mnt|opt)/)", re.I),
    ),
    ("带凭据的网址", re.compile(r"https?://[^\s/@:]+:[^\s/@]+@", re.I)),
)


def public_metadata(source_object):
    source = source_object.metadata_json or {}
    metadata = {
        field: source[field]
        for field in PUBLIC_METADATA_FIELDS
        if source.get(field) not in (None, "", [])
    }
    external_url = metadata.get("external_url", "")
    if external_url and not str(external_url).lower().startswith(("https://", "http://")):
        metadata.pop("external_url", None)
    return metadata


def unique_public_slug(owner, title, exclude_pk=None):
    base = slugify(title, allow_unicode=True)[:190] or "research-note"
    candidate = base
    number = 2
    queryset = PublicationSnapshot.objects.filter(owner=owner)
    if exclude_pk:
        queryset = queryset.exclude(pk=exclude_pk)
    while queryset.filter(public_slug=candidate).exists():
        candidate = f"{base[:185]}-{number}"
        number += 1
    return candidate


def sensitive_findings(snapshot):
    searchable = "\n".join(
        (
            snapshot.title or "",
            snapshot.summary or "",
            snapshot.content_markdown or "",
            snapshot.public_project_name or "",
            snapshot.public_project_summary or "",
        )
    )
    return [label for label, pattern in SENSITIVE_PATTERNS if pattern.search(searchable)]


def attachment_is_publishable(attachment):
    return (
        Path(attachment.original_name).suffix.lower() in PUBLIC_ATTACHMENT_EXTENSIONS
        and attachment.file.storage.exists(attachment.file.name)
    )


@transaction.atomic
def sync_public_attachments(snapshot, selected_attachments):
    selected = {attachment.pk: attachment for attachment in selected_attachments}
    existing = {
        item.source_attachment_id: item
        for item in snapshot.public_attachments.exclude(source_attachment=None)
    }
    for source_id, item in existing.items():
        if source_id not in selected:
            item.delete()
    for source_id, source in selected.items():
        if source_id in existing:
            continue
        with source.file.open("rb") as source_file:
            content = ContentFile(source_file.read())
        copy = PublishedAttachment(
            snapshot=snapshot,
            source_attachment=source,
            original_name=Path(source.original_name).name,
            mime_type=source.mime_type,
            size=source.size,
            sha256=source.sha256,
        )
        copy.file.save(copy.original_name, content, save=False)
        copy.save()
