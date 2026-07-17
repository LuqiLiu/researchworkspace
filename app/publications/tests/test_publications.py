import hashlib
import json
import zipfile
from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from app.audit.models import SecurityAuditLog
from app.comments.models import Comment
from app.research_objects.models import Attachment, ResearchObject, Tag
from app.sharing.models import ObjectShare

from app.publications.models import PublicationSnapshot


class PublicationSnapshotTests(TestCase):
    def setUp(self):
        self.media = TemporaryDirectory()
        self.settings_override = override_settings(MEDIA_ROOT=self.media.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(self.media.cleanup)

        User = get_user_model()
        self.owner = User.objects.create_user("owner", password="test-password")
        self.collaborator = User.objects.create_user("collaborator", password="test-password")
        profile = self.owner.profile
        profile.display_name = "Dr. Owner"
        profile.bio = "Computational research"
        profile.public_enabled = True
        profile.save()
        self.source = ResearchObject.objects.create(
            owner=self.owner,
            object_type=ResearchObject.ObjectType.PAPER,
            title="A Reproducible Result",
            content_markdown="## Public finding\n\nA stable result.",
            metadata_json={
                "authors": ["Ada Researcher"],
                "year": 2026,
                "journal": "Open Methods",
                "doi": "10.1000/example",
                "external_url": "javascript:alert(1)",
                "bibtex": "PRIVATE-BIBTEX",
                "private_note": "PRIVATE-METADATA",
            },
        )
        private_tag = Tag.objects.create(owner=self.owner, name="secret-tag")
        self.source.tags.add(private_tag)
        Comment.objects.create(
            research_object=self.source,
            author=self.collaborator,
            content="PRIVATE-COMMENT",
        )
        ObjectShare.objects.create(
            research_object=self.source,
            user=self.collaborator,
            permission=ObjectShare.Permission.VIEWER,
            created_by=self.owner,
        )

    def _payload(self, **overrides):
        data = {
            "title": "Public Result",
            "public_slug": "public-result",
            "summary": "A carefully reviewed public summary.",
            "content_markdown": "## Public finding\n\nA stable result.",
            "public_project_name": "Open Research",
            "public_project_summary": "Public project context only.",
        }
        data.update(overrides)
        return data

    def _create_draft(self, **overrides):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("publications:edit_from_source", args=[self.source.pk]),
            self._payload(**overrides),
        )
        self.assertRedirects(
            response,
            reverse("publications:preview", args=[self.source.publication_snapshot.pk]),
        )
        return PublicationSnapshot.objects.get(source_object=self.source)

    def _publish(self, snapshot):
        self.client.force_login(self.owner)
        return self.client.post(reverse("publications:publish", args=[snapshot.pk]))

    def test_draft_is_independent_and_whitelists_metadata(self):
        snapshot = self._create_draft()

        self.assertFalse(snapshot.is_published)
        self.assertEqual(snapshot.content_markdown, "## Public finding\n\nA stable result.")
        self.assertEqual(snapshot.metadata_json["doi"], "10.1000/example")
        self.assertNotIn("bibtex", snapshot.metadata_json)
        self.assertNotIn("private_note", snapshot.metadata_json)
        self.assertNotIn("external_url", snapshot.metadata_json)
        preview = self.client.get(reverse("publications:preview", args=[snapshot.pk]))
        self.assertNotContains(preview, "PRIVATE-COMMENT")
        self.assertNotContains(preview, "secret-tag")
        self.assertNotContains(preview, "collaborator")

    def test_published_page_is_public_and_source_edits_do_not_sync(self):
        snapshot = self._create_draft()
        self._publish(snapshot)
        snapshot.refresh_from_db()
        self.assertTrue(snapshot.is_published)

        self.source.content_markdown = "PRIVATE LATER EDIT"
        self.source.title = "Private changed title"
        self.source.save()

        self.client.logout()
        url = reverse(
            "publications:public_detail",
            args=[self.owner.profile.public_slug, snapshot.public_slug],
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A stable result")
        self.assertNotContains(response, "PRIVATE LATER EDIT")
        self.assertContains(response, 'content="index,follow"')

    def test_draft_and_disabled_profile_are_not_public(self):
        snapshot = self._create_draft()
        public_url = reverse(
            "publications:public_detail",
            args=[self.owner.profile.public_slug, snapshot.public_slug],
        )
        self.client.logout()
        self.assertEqual(self.client.get(public_url).status_code, 404)

        self._publish(snapshot)
        profile = self.owner.profile
        profile.public_enabled = False
        profile.save()
        self.client.logout()
        self.assertEqual(self.client.get(public_url).status_code, 404)

    def test_sensitive_material_blocks_publication(self):
        snapshot = self._create_draft(content_markdown="token = super-secret")
        response = self._publish(snapshot)

        snapshot.refresh_from_db()
        self.assertFalse(snapshot.is_published)
        self.assertRedirects(response, reverse("publications:preview", args=[snapshot.pk]))
        preview = self.client.get(reverse("publications:preview", args=[snapshot.pk]))
        self.assertContains(preview, "发布已锁定")

    def test_sensitive_edit_automatically_withdraws_published_snapshot(self):
        snapshot = self._create_draft()
        self._publish(snapshot)
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("publications:edit_from_source", args=[self.source.pk]),
            self._payload(content_markdown="password = leaked-value"),
        )

        self.assertRedirects(response, reverse("publications:preview", args=[snapshot.pk]))
        snapshot.refresh_from_db()
        self.assertFalse(snapshot.is_published)
        public_url = reverse(
            "publications:public_detail",
            args=[self.owner.profile.public_slug, snapshot.public_slug],
        )
        self.client.logout()
        self.assertEqual(self.client.get(public_url).status_code, 404)

    def test_non_owner_cannot_manage_snapshot(self):
        snapshot = self._create_draft()
        self.client.force_login(self.collaborator)

        self.assertEqual(
            self.client.get(reverse("publications:edit_from_source", args=[self.source.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(reverse("publications:preview", args=[snapshot.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(reverse("publications:publish", args=[snapshot.pk])).status_code,
            404,
        )

    def test_withdrawal_immediately_removes_public_page_and_is_audited(self):
        snapshot = self._create_draft()
        self._publish(snapshot)
        public_url = reverse(
            "publications:public_detail",
            args=[self.owner.profile.public_slug, snapshot.public_slug],
        )
        self.client.force_login(self.owner)
        response = self.client.post(reverse("publications:withdraw", args=[snapshot.pk]))

        self.assertRedirects(response, reverse("publications:preview", args=[snapshot.pk]))
        self.client.logout()
        self.assertEqual(self.client.get(public_url).status_code, 404)
        self.assertTrue(
            SecurityAuditLog.objects.filter(
                event_type=SecurityAuditLog.EventType.PUBLICATION_WITHDRAWN,
                resource_id=snapshot.pk,
            ).exists()
        )

    def test_attachment_requires_rights_confirmation(self):
        content = b"%PDF-1.4 public sample"
        attachment = Attachment.objects.create(
            owner=self.owner,
            research_object=self.source,
            file=SimpleUploadedFile("paper.pdf", content, content_type="application/pdf"),
            original_name="paper.pdf",
            mime_type="application/pdf",
            size=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
        )
        self.client.force_login(self.owner)
        payload = self._payload(public_attachments=[attachment.pk])
        response = self.client.post(
            reverse("publications:edit_from_source", args=[self.source.pk]),
            payload,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "必须确认发布权利")
        self.assertFalse(PublicationSnapshot.objects.exists())

    def test_selected_attachment_is_copied_and_public_only_after_publish(self):
        content = b"%PDF-1.4 public sample"
        source_attachment = Attachment.objects.create(
            owner=self.owner,
            research_object=self.source,
            file=SimpleUploadedFile("paper.pdf", content, content_type="application/pdf"),
            original_name="paper.pdf",
            mime_type="application/pdf",
            size=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
        )
        snapshot = self._create_draft(
            public_attachments=[source_attachment.pk],
            confirm_attachment_rights="on",
        )
        public_copy = snapshot.public_attachments.get()
        self.assertNotEqual(public_copy.file.name, source_attachment.file.name)

        public_download = reverse("publications:public_attachment", args=[public_copy.pk])
        self.client.logout()
        self.assertEqual(self.client.get(public_download).status_code, 404)
        self._publish(snapshot)
        self.client.logout()
        response = self.client.get(public_download)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Disposition"], 'attachment; filename="paper.pdf"')

    def test_public_profile_and_robots_are_available_without_login(self):
        snapshot = self._create_draft()
        self._publish(snapshot)
        self.client.logout()

        profile_url = reverse("publications:public_profile", args=[self.owner.profile.public_slug])
        profile_response = self.client.get(profile_url)
        self.assertEqual(profile_response.status_code, 200)
        self.assertContains(profile_response, "Dr. Owner")
        self.assertContains(profile_response, "Public Result")
        robots = self.client.get(reverse("publications:robots"))
        self.assertContains(robots, "Allow: /u/")
        self.assertContains(robots, "Disallow: /")

    def test_owner_can_export_only_published_public_profile_content(self):
        snapshot = self._create_draft()
        self._publish(snapshot)
        private_source = ResearchObject.objects.create(
            owner=self.owner,
            title="Private draft source",
            content_markdown="PRIVATE-DRAFT-CONTENT",
        )
        PublicationSnapshot.objects.create(
            source_object=private_source,
            owner=self.owner,
            public_slug="private-draft",
            title="Private draft",
            content_markdown="PRIVATE-DRAFT-CONTENT",
        )
        self.client.force_login(self.owner)
        response = self.client.get(reverse("publications:profile_export"))
        self.assertEqual(response.status_code, 200)
        payload = b"".join(response.streaming_content)
        with zipfile.ZipFile(BytesIO(payload)) as archive:
            manifest = json.loads(archive.read("profile.json"))
            self.assertEqual(len(manifest["snapshots"]), 1)
            self.assertEqual(manifest["snapshots"][0]["title"], "Public Result")
            exported_markdown = archive.read(
                manifest["snapshots"][0]["markdown_path"]
            ).decode()
            self.assertIn("A stable result", exported_markdown)
            self.assertNotIn("PRIVATE-DRAFT-CONTENT", exported_markdown)
