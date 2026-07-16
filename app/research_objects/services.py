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


def visible_objects(user):
    from .models import ResearchObject

    return ResearchObject.objects.visible_to(user).prefetch_related("tags")


def search_objects(user, query):
    queryset = visible_objects(user)
    query = (query or "").strip()
    if not query:
        return queryset.none()
    return queryset.filter(
        Q(title__icontains=query)
        | Q(content_plain_text__icontains=query)
        | Q(tags__name__icontains=query)
    ).distinct()
