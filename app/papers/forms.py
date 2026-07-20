from django import forms

from .services import make_bibtex, normalize_doi, safe_metadata_text


class PaperImportForm(forms.Form):
    doi = forms.CharField(
        label="DOI",
        required=False,
        help_text="例如 10.1038/s41586-024-00000-0",
    )
    external_url = forms.URLField(
        label="论文网页",
        required=False,
    )
    pdf = forms.FileField(
        label="PDF 文件",
        required=False,
        help_text="仅读取文档元数据和前两页文本，不执行 OCR。",
    )
    title = forms.CharField(
        label="标题（可选）",
        required=False,
        max_length=240,
    )
    personal_note = forms.CharField(
        label="一句话笔记",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    is_shared_with_team = forms.BooleanField(
        label="加入团队知识库",
        required=False,
        initial=True,
        help_text="团队成员可以查看和评论；只有你可以编辑。",
    )
    share_team_attachments = forms.BooleanField(
        label="团队成员也可访问 PDF",
        required=False,
        initial=False,
    )

    def clean_pdf(self):
        upload = self.cleaned_data.get("pdf")
        if not upload:
            return upload
        if upload.size > 50 * 1024 * 1024:
            raise forms.ValidationError("PDF 不能超过 50 MB。")
        if not upload.name.lower().endswith(".pdf"):
            raise forms.ValidationError("请选择 PDF 文件。")
        header = upload.read(1024)
        upload.seek(0)
        if b"%PDF-" not in header:
            raise forms.ValidationError("文件内容不是有效的 PDF。")
        if (upload.content_type or "").lower() not in {
            "application/pdf",
            "application/octet-stream",
        }:
            raise forms.ValidationError("PDF 的 MIME 类型不正确。")
        return upload

    def clean(self):
        cleaned_data = super().clean()
        if not any(
            cleaned_data.get(name)
            for name in ("doi", "external_url", "pdf", "title")
        ):
            raise forms.ValidationError("请至少提供 DOI、论文网页、PDF 或标题。")
        if cleaned_data.get("share_team_attachments") and not cleaned_data.get(
            "is_shared_with_team"
        ):
            self.add_error(
                "share_team_attachments",
                "必须先将文献加入团队知识库。",
            )
        return cleaned_data


class PaperMetadataForm(forms.Form):
    title = forms.CharField(label="标题", max_length=240)
    authors = forms.CharField(
        label="作者",
        required=False,
        help_text="每行一位作者。",
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    year = forms.IntegerField(label="年份", required=False, min_value=0, max_value=9999)
    journal = forms.CharField(label="期刊或会议", required=False, max_length=240)
    doi = forms.CharField(label="DOI", required=False, max_length=255)
    external_url = forms.URLField(label="外部链接", required=False)
    abstract = forms.CharField(
        label="摘要",
        required=False,
        widget=forms.Textarea(attrs={"rows": 7}),
    )
    bibtex = forms.CharField(
        label="BibTeX",
        required=False,
        widget=forms.Textarea(attrs={"rows": 9, "class": "code-input"}),
    )

    def __init__(self, *args, research_object, **kwargs):
        self.research_object = research_object
        metadata = research_object.metadata_json or {}
        kwargs.setdefault(
            "initial",
            {
                "title": research_object.title,
                "authors": "\n".join(metadata.get("authors", [])),
                "year": metadata.get("year"),
                "journal": metadata.get("journal", ""),
                "doi": metadata.get("doi", ""),
                "external_url": metadata.get("external_url", ""),
                "abstract": metadata.get("abstract", ""),
                "bibtex": metadata.get("bibtex", ""),
            },
        )
        super().__init__(*args, **kwargs)

    def clean_doi(self):
        raw_doi = self.cleaned_data.get("doi", "")
        if not raw_doi:
            return ""
        doi = normalize_doi(raw_doi)
        if not doi:
            raise forms.ValidationError("DOI 格式不正确。")
        return doi

    def save(self):
        obj = self.research_object
        metadata = dict(obj.metadata_json or {})
        authors = [
            safe_metadata_text(name, 200)
            for name in self.cleaned_data["authors"].splitlines()
            if safe_metadata_text(name, 200)
        ][:100]
        fields = {
            "title": safe_metadata_text(self.cleaned_data["title"], 240),
            "authors": authors,
            "year": self.cleaned_data.get("year"),
            "journal": safe_metadata_text(self.cleaned_data.get("journal"), 240),
            "doi": self.cleaned_data.get("doi", ""),
            "external_url": self.cleaned_data.get("external_url", ""),
            "abstract": safe_metadata_text(self.cleaned_data.get("abstract"), 10000),
            "bibtex": self.cleaned_data.get("bibtex", "").strip(),
        }
        if not fields["bibtex"]:
            fields["bibtex"] = make_bibtex(fields)
        metadata.update(fields)
        metadata["normalized_title"] = "".join(
            character
            for character in fields["title"].casefold()
            if character.isalnum()
        )
        metadata["metadata_source"] = "manual"
        provenance = dict(metadata.get("metadata_provenance") or {})
        for name in fields:
            provenance[name] = {"source": "manual", "confidence": "high"}
        metadata["metadata_provenance"] = provenance
        obj.title = fields["title"]
        obj.metadata_json = metadata
        obj.save()
        return obj
