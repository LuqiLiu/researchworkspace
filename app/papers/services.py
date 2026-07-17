import hashlib
import html
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from pypdf import PdfReader

from app.research_objects.models import Attachment, ResearchObject
from app.accounts.services import reserve_storage

DOI_PATTERN = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
ARXIV_PATTERN = re.compile(
    r"(?:arxiv:\s*)?((?:[a-z-]+(?:\.[A-Z]{2})?/\d{7}|\d{4}\.\d{4,5})(?:v\d+)?)",
    re.IGNORECASE,
)


def safe_metadata_text(value, max_length):
    value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", str(value or ""))
    return re.sub(r"\s+", " ", value).strip()[:max_length]


def normalize_doi(value):
    value = (value or "").strip()
    value = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value, flags=re.I)
    value = re.sub(r"^doi:\s*", "", value, flags=re.I)
    match = DOI_PATTERN.search(value)
    return match.group(0).rstrip(".,;)").lower() if match else ""


def normalize_arxiv_id(value):
    match = ARXIV_PATTERN.search(value or "")
    return match.group(1) if match else ""


def _merge_metadata(metadata, incoming, *, source, confidence):
    provenance = metadata.setdefault("metadata_provenance", {})
    for name, value in incoming.items():
        if name == "metadata_source" or value in (None, "", []):
            continue
        metadata[name] = value
        provenance[name] = {"source": source, "confidence": confidence}
    metadata["metadata_source"] = source


def _plain_abstract(value):
    value = html.unescape(value or "")
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value)).strip()


def crossref_metadata(doi):
    normalized = normalize_doi(doi)
    if not normalized:
        return {}
    url = f"https://api.crossref.org/works/{quote(normalized, safe='')}"
    user_agent = "ResearchWorkspaceLite/1.0"
    if settings.CROSSREF_MAILTO:
        user_agent += f" (mailto:{settings.CROSSREF_MAILTO})"
    request = Request(url, headers={"User-Agent": user_agent})
    try:
        with urlopen(request, timeout=settings.CROSSREF_TIMEOUT_SECONDS) as response:
            payload = json.load(response)
    except (HTTPError, URLError, TimeoutError, ValueError, OSError):
        return {}
    message = payload.get("message", {})
    authors = []
    for author in message.get("author", []):
        name = " ".join(
            part for part in (author.get("given", ""), author.get("family", "")) if part
        ).strip()
        if name:
            authors.append(name)
    date_parts = (
        message.get("published-print")
        or message.get("published-online")
        or message.get("issued")
        or {}
    ).get("date-parts", [[]])
    year = date_parts[0][0] if date_parts and date_parts[0] else None
    return {
        "doi": normalize_doi(message.get("DOI", normalized)),
        "title": safe_metadata_text((message.get("title") or [""])[0], 240),
        "authors": [safe_metadata_text(author, 200) for author in authors[:100]],
        "year": year,
        "journal": safe_metadata_text((message.get("container-title") or [""])[0], 240),
        "abstract": _plain_abstract(message.get("abstract", "")),
        "external_url": message.get("URL", ""),
        "metadata_source": "crossref",
    }


def arxiv_metadata(arxiv_id):
    normalized = normalize_arxiv_id(arxiv_id)
    if not normalized:
        return {}
    url = f"https://export.arxiv.org/api/query?id_list={quote(normalized, safe='/')}"
    request = Request(
        url,
        headers={"User-Agent": "ResearchWorkspaceLite/1.0"},
    )
    try:
        with urlopen(request, timeout=settings.CROSSREF_TIMEOUT_SECONDS) as response:
            root = ET.parse(response).getroot()
    except (HTTPError, URLError, TimeoutError, ET.ParseError, OSError):
        return {}
    atom = {"atom": "http://www.w3.org/2005/Atom"}
    entry = root.find("atom:entry", atom)
    if entry is None:
        return {}

    def text(path):
        node = entry.find(path, atom)
        return node.text.strip() if node is not None and node.text else ""

    authors = [
        safe_metadata_text(node.text, 200)
        for node in entry.findall("atom:author/atom:name", atom)
        if node.text
    ][:100]
    published = text("atom:published")
    return {
        "arxiv_id": normalized,
        "title": safe_metadata_text(text("atom:title"), 240),
        "authors": authors,
        "year": int(published[:4]) if published[:4].isdigit() else None,
        "abstract": safe_metadata_text(text("atom:summary"), 10000),
        "external_url": f"https://arxiv.org/abs/{normalized}",
        "metadata_source": "arxiv",
    }


def pdf_metadata(upload):
    upload.seek(0)
    reader = PdfReader(upload, strict=False)
    metadata = reader.metadata
    extracted = {
        "title": safe_metadata_text(getattr(metadata, "title", ""), 240),
        "authors": [safe_metadata_text(getattr(metadata, "author", ""), 200)],
        "pdf_page_count": len(reader.pages),
        "metadata_source": "pdf",
    }
    extracted["authors"] = [name for name in extracted["authors"] if name]
    first_pages = []
    for page in reader.pages[:2]:
        try:
            first_pages.append(page.extract_text() or "")
        except Exception:
            continue
    first_text = "\n".join(first_pages)[:50000]
    doi_match = DOI_PATTERN.search(first_text)
    if doi_match:
        extracted["doi"] = normalize_doi(doi_match.group(0))
    extracted["pdf_first_pages_text"] = first_text
    upload.seek(0)
    return extracted


def make_bibtex(metadata):
    doi = metadata.get("doi", "")
    authors = metadata.get("authors", [])
    if isinstance(authors, str):
        authors = [authors]
    first_family = "paper"
    if authors:
        first_family = re.sub(r"[^a-z0-9]", "", authors[0].split()[-1].lower()) or "paper"
    key = f"{first_family}{metadata.get('year') or 'nd'}"
    fields = {
        "title": metadata.get("title"),
        "author": " and ".join(authors),
        "journal": metadata.get("journal"),
        "year": metadata.get("year"),
        "doi": doi,
        "url": metadata.get("external_url"),
    }
    lines = [f"@article{{{key},"]
    for name, value in fields.items():
        if value:
            safe_value = str(value).replace("{", "\\{").replace("}", "\\}")
            lines.append(f"  {name} = {{{safe_value}}},")
    lines.append("}")
    return "\n".join(lines)


def duplicate_candidates(owner, metadata, pdf_sha256=""):
    queryset = ResearchObject.objects.active().filter(
        owner=owner,
        object_type=ResearchObject.ObjectType.PAPER,
    )
    doi = metadata.get("doi")
    normalized_title = metadata.get("normalized_title")
    candidates = queryset.none()
    if doi:
        candidates = queryset.filter(metadata_json__doi=doi)
    if normalized_title:
        candidates = candidates | queryset.filter(
            metadata_json__normalized_title=normalized_title
        )
    if pdf_sha256:
        candidates = candidates | queryset.filter(
            attachments__sha256=pdf_sha256
        )
    return candidates.distinct()


@transaction.atomic
def import_paper(*, owner, cleaned_data):
    upload = cleaned_data.get("pdf")
    supplied_doi = normalize_doi(cleaned_data.get("doi")) or normalize_doi(
        cleaned_data.get("external_url")
    )
    metadata = {
        "doi": supplied_doi,
        "external_url": cleaned_data.get("external_url") or "",
        "metadata_provenance": {},
    }
    for name in ("doi", "external_url"):
        if metadata[name]:
            metadata["metadata_provenance"][name] = {
                "source": "manual",
                "confidence": "high",
            }
    pdf_sha256 = ""
    pdf_bytes = b""
    if upload:
        pdf_bytes = upload.read()
        pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
        upload.seek(0)
        try:
            _merge_metadata(
                metadata,
                pdf_metadata(upload),
                source="pdf",
                confidence="medium",
            )
        except Exception as exc:
            metadata["pdf_metadata_error"] = exc.__class__.__name__
    doi = supplied_doi or metadata.get("doi", "")
    arxiv_id = normalize_arxiv_id(cleaned_data.get("external_url"))
    remote = crossref_metadata(doi) if doi else arxiv_metadata(arxiv_id)
    if remote:
        source = remote.get("metadata_source", "external")
        _merge_metadata(metadata, remote, source=source, confidence="high")
    title = safe_metadata_text(cleaned_data.get("title") or metadata.get("title"), 240)
    if not title and upload:
        title = Path(upload.name).stem
    title = title or doi or cleaned_data.get("external_url") or "未命名文献"
    metadata["title"] = title
    if cleaned_data.get("title"):
        metadata["metadata_provenance"]["title"] = {
            "source": "manual",
            "confidence": "high",
        }
    elif "title" not in metadata["metadata_provenance"]:
        metadata["metadata_provenance"]["title"] = {
            "source": "derived",
            "confidence": "low",
        }
    metadata["normalized_title"] = re.sub(r"\W+", "", title.casefold())
    metadata["bibtex"] = make_bibtex(metadata)
    duplicates = list(duplicate_candidates(owner, metadata, pdf_sha256))
    obj = ResearchObject.objects.create(
        owner=owner,
        object_type=ResearchObject.ObjectType.PAPER,
        title=title,
        content_markdown=cleaned_data.get("personal_note") or "",
        metadata_json=metadata,
    )
    if upload:
        reserve_storage(owner, len(pdf_bytes))
        Attachment.objects.create(
            owner=owner,
            research_object=obj,
            file=ContentFile(pdf_bytes, name=Path(upload.name).name),
            original_name=Path(upload.name).name,
            mime_type="application/pdf",
            size=len(pdf_bytes),
            sha256=pdf_sha256,
        )
    return obj, duplicates, bool(remote)
