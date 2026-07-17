from django import forms


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

    def clean_pdf(self):
        upload = self.cleaned_data.get("pdf")
        if not upload:
            return upload
        if upload.size > 50 * 1024 * 1024:
            raise forms.ValidationError("PDF 不能超过 50 MB。")
        if not upload.name.lower().endswith(".pdf"):
            raise forms.ValidationError("请选择 PDF 文件。")
        return upload

    def clean(self):
        cleaned_data = super().clean()
        if not any(
            cleaned_data.get(name)
            for name in ("doi", "external_url", "pdf", "title")
        ):
            raise forms.ValidationError("请至少提供 DOI、论文网页、PDF 或标题。")
        return cleaned_data
