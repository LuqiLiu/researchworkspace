import re

import bleach
import markdown
from django.db.models import Q
from django.utils.html import strip_tags

ALLOWED_TAGS = [
    "a", "blockquote", "br", "code", "del", "em", "h1", "h2", "h3",
    "h4", "h5", "h6", "hr", "li", "ol", "p", "pre", "strong", "table",
    "tbody", "td", "th", "thead", "tr", "ul",
]
ALLOWED_ATTRIBUTES = {"a": ["href", "title", "rel"]}


def render_markdown(value):
    rendered = markdown.markdown(
        value or "",
        extensions=["fenced_code", "tables", "sane_lists"],
    )
    return bleach.clean(
        rendered,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=["http", "https", "mailto"],
        strip=True,
    )


def markdown_to_plain_text(value):
    rendered = markdown.markdown(value or "")
    plain = strip_tags(rendered)
    return re.sub(r"\s+", " ", plain).strip()


def compose_search_text(obj):
    metadata = obj.metadata_json or {}
    authors = metadata.get("authors", [])
    if isinstance(authors, list):
        authors = " ".join(str(author) for author in authors)
    parts = [
        obj.title,
        obj.content_plain_text,
        authors,
        metadata.get("doi", ""),
        metadata.get("journal", ""),
        metadata.get("abstract", ""),
        metadata.get("bibtex", ""),
        metadata.get("external_url", ""),
    ]
    return re.sub(r"\s+", " ", " ".join(str(part or "") for part in parts)).strip()


def visible_objects(user):
    from app.sharing.services import visible_objects as shared_visible_objects

    return shared_visible_objects(user)


def search_objects(user, query):
    queryset = visible_objects(user)
    query = (query or "").strip()
    if not query:
        return queryset.none()
    return queryset.filter(
        Q(title__icontains=query)
        | Q(search_text__icontains=query)
        | Q(tags__name__icontains=query)
        | Q(project__name__icontains=query)
        | Q(comments__content__icontains=query, comments__deleted_at__isnull=True)
    ).distinct()
