from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from pypdf import PdfWriter

from app.papers.forms import PaperImportForm
from app.papers.services import import_paper, normalize_arxiv_id, normalize_doi
from app.research_objects.models import ResearchObject


class PaperImportTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            "paper-owner",
            password="password",
        )
        self.other = get_user_model().objects.create_user(
            "paper-other",
            password="password",
        )

    def test_normalize_doi_accepts_common_forms(self):
        self.assertEqual(
            normalize_doi("https://doi.org/10.1000/ABC.123"),
            "10.1000/abc.123",
        )

    def test_normalize_arxiv_id_accepts_public_urls(self):
        self.assertEqual(
            normalize_arxiv_id("https://arxiv.org/abs/2501.01234v2"),
            "2501.01234v2",
        )

    @patch("app.papers.services.crossref_metadata", return_value={})
    def test_external_metadata_failure_does_not_block_save(self, metadata_mock):
        obj, duplicates, remote_loaded = import_paper(
            owner=self.owner,
            cleaned_data={
                "doi": "10.1000/example",
                "external_url": "",
                "pdf": None,
                "title": "Fallback title",
                "personal_note": "Useful paper",
            },
        )
        self.assertEqual(obj.title, "Fallback title")
        self.assertEqual(obj.object_type, ResearchObject.ObjectType.PAPER)
        self.assertTrue(obj.is_shared_with_team)
        self.assertEqual(obj.status, ResearchObject.Status.SHARED)
        self.assertFalse(remote_loaded)
        self.assertEqual(duplicates, [])
        metadata_mock.assert_called_once_with("10.1000/example")

    @patch("app.papers.services.crossref_metadata")
    def test_doi_metadata_and_bibtex_are_saved(self, metadata_mock):
        metadata_mock.return_value = {
            "doi": "10.1000/example",
            "title": "A Research Result",
            "authors": ["Ada Lovelace", "Alan Turing"],
            "year": 2025,
            "journal": "Journal of Tests",
            "external_url": "https://doi.org/10.1000/example",
        }
        obj, _, remote_loaded = import_paper(
            owner=self.owner,
            cleaned_data={
                "doi": "10.1000/example",
                "external_url": "",
                "pdf": None,
                "title": "",
                "personal_note": "",
            },
        )
        self.assertTrue(remote_loaded)
        self.assertEqual(obj.title, "A Research Result")
        self.assertIn("Ada Lovelace and Alan Turing", obj.metadata_json["bibtex"])
        self.assertIn("Journal of Tests", obj.search_text)
        self.assertEqual(
            obj.metadata_json["metadata_provenance"]["title"]["confidence"],
            "high",
        )

    @patch("app.papers.services.arxiv_metadata")
    def test_arxiv_url_uses_arxiv_provider(self, metadata_mock):
        metadata_mock.return_value = {
            "arxiv_id": "2501.01234",
            "title": "Open preprint",
            "authors": ["Researcher One"],
            "year": 2025,
            "external_url": "https://arxiv.org/abs/2501.01234",
            "metadata_source": "arxiv",
        }
        obj, _, remote_loaded = import_paper(
            owner=self.owner,
            cleaned_data={
                "doi": "",
                "external_url": "https://arxiv.org/abs/2501.01234",
                "pdf": None,
                "title": "",
                "personal_note": "",
            },
        )
        self.assertTrue(remote_loaded)
        self.assertEqual(obj.title, "Open preprint")
        self.assertEqual(obj.metadata_json["arxiv_id"], "2501.01234")
        self.assertEqual(
            obj.metadata_json["metadata_provenance"]["title"],
            {"source": "arxiv", "confidence": "high"},
        )
        metadata_mock.assert_called_once_with("2501.01234")

    def test_owner_can_manually_correct_all_paper_metadata(self):
        obj = ResearchObject.objects.create(
            owner=self.owner,
            object_type=ResearchObject.ObjectType.PAPER,
            title="Imported title",
            content_markdown="Personal note",
            metadata_json={"title": "Imported title", "metadata_source": "pdf"},
        )
        url = reverse("papers:metadata_edit", args=[obj.pk])
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.owner)
        response = self.client.post(
            url,
            {
                "title": "Corrected title",
                "authors": "Ada Lovelace\nAlan Turing",
                "year": 2026,
                "journal": "Verified Journal",
                "doi": "https://doi.org/10.1000/CORRECT",
                "external_url": "https://example.org/paper",
                "abstract": "Corrected abstract",
                "bibtex": "",
            },
        )
        self.assertRedirects(
            response,
            reverse("research_objects:detail", args=[obj.pk]),
        )
        obj.refresh_from_db()
        self.assertEqual(obj.title, "Corrected title")
        self.assertEqual(obj.metadata_json["authors"], ["Ada Lovelace", "Alan Turing"])
        self.assertEqual(obj.metadata_json["doi"], "10.1000/correct")
        self.assertEqual(obj.metadata_json["metadata_source"], "manual")
        self.assertIn("Verified Journal", obj.search_text)

    @patch("app.papers.services.crossref_metadata", return_value={})
    def test_pdf_is_private_attachment_and_duplicate_is_reported(self, _mock):
        buffer = BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.add_metadata({"/Title": "PDF title", "/Author": "Researcher"})
        writer.write(buffer)
        payload = buffer.getvalue()

        first, _, _ = import_paper(
            owner=self.owner,
            cleaned_data={
                "doi": "",
                "external_url": "",
                "pdf": SimpleUploadedFile("paper.pdf", payload, content_type="application/pdf"),
                "title": "",
                "personal_note": "",
            },
        )
        second, duplicates, _ = import_paper(
            owner=self.owner,
            cleaned_data={
                "doi": "",
                "external_url": "",
                "pdf": SimpleUploadedFile("copy.pdf", payload, content_type="application/pdf"),
                "title": "",
                "personal_note": "",
            },
        )
        self.assertEqual(first.attachments.count(), 1)
        self.assertEqual(second.attachments.count(), 1)
        self.assertIn(first, duplicates)

    def test_bibtex_export_obeys_object_visibility(self):
        obj = ResearchObject.objects.create(
            owner=self.owner,
            object_type=ResearchObject.ObjectType.PAPER,
            title="Private paper",
            content_markdown="",
            metadata_json={"bibtex": "@article{private}"},
        )
        url = reverse("papers:bibtex", args=[obj.pk])
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.owner)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "@article{private}")

    def test_csv_export_contains_only_owner_papers(self):
        ResearchObject.objects.create(
            owner=self.owner,
            object_type=ResearchObject.ObjectType.PAPER,
            title="Owned paper",
            content_markdown="My note",
            metadata_json={
                "authors": ["Ada Lovelace"],
                "year": 2026,
                "doi": "10.1000/owned",
            },
        )
        ResearchObject.objects.create(
            owner=self.other,
            object_type=ResearchObject.ObjectType.PAPER,
            title="Other private paper",
            content_markdown="Secret",
        )
        self.client.force_login(self.owner)
        response = self.client.get(reverse("papers:csv_export"))
        body = response.content.decode("utf-8-sig")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Owned paper", body)
        self.assertIn("10.1000/owned", body)
        self.assertNotIn("Other private paper", body)

    def test_fake_pdf_is_rejected_by_content_and_mime_type(self):
        form = PaperImportForm(
            files={
                "pdf": SimpleUploadedFile(
                    "fake.pdf",
                    b"<html>not a pdf</html>",
                    content_type="text/html",
                )
            }
        )
        self.assertFalse(form.is_valid())

    @patch("app.papers.services.crossref_metadata", return_value={})
    def test_long_pdf_metadata_title_is_safely_truncated(self, _mock):
        buffer = BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.add_metadata({"/Title": "T" * 300})
        writer.write(buffer)
        obj, _, _ = import_paper(
            owner=self.owner,
            cleaned_data={
                "doi": "",
                "external_url": "",
                "pdf": SimpleUploadedFile(
                    "long-title.pdf",
                    buffer.getvalue(),
                    content_type="application/pdf",
                ),
                "title": "",
                "personal_note": "",
            },
        )
        self.assertEqual(len(obj.title), 240)
