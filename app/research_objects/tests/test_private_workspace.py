import tempfile
import json
import zipfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from app.research_objects.models import Attachment, ObjectRelation, ResearchObject
from app.research_objects.forms import AttachmentForm
from app.research_objects.services import render_markdown


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class PrivateWorkspaceTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.alice = users.objects.create_user("alice", password="password")
        self.bob = users.objects.create_user("bob", password="password")
        self.obj = ResearchObject.objects.create(
            owner=self.alice,
            title="Private experiment",
            content_markdown="# Secret\nresult 42",
        )

    def test_new_object_is_private_by_default(self):
        self.assertEqual(self.obj.status, ResearchObject.Status.PRIVATE)
        self.assertEqual(list(ResearchObject.objects.visible_to(self.bob)), [])

    def test_create_view_assigns_current_user_and_tags(self):
        self.client.force_login(self.alice)
        response = self.client.post(
            reverse("research_objects:create"),
            {
                "object_type": ResearchObject.ObjectType.IDEA,
                "title": "New idea",
                "content_markdown": "Try this",
                "tag_names": "ML, optimization",
            },
        )
        created = ResearchObject.objects.get(title="New idea")
        self.assertRedirects(
            response,
            reverse("research_objects:detail", args=[created.pk]),
        )
        self.assertEqual(created.owner, self.alice)
        self.assertEqual(created.status, ResearchObject.Status.PRIVATE)
        self.assertEqual(
            set(created.tags.values_list("name", flat=True)),
            {"ML", "optimization"},
        )

    def test_other_user_cannot_guess_detail_edit_or_export_urls(self):
        self.client.force_login(self.bob)
        urls = [
            reverse("research_objects:detail", args=[self.obj.pk]),
            reverse("research_objects:edit", args=[self.obj.pk]),
            reverse("research_objects:export", args=[self.obj.pk]),
        ]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 404)

    def test_other_user_cannot_autosave_guessed_object(self):
        self.client.force_login(self.bob)
        response = self.client.post(
            reverse("research_objects:autosave", args=[self.obj.pk]),
            {
                "object_type": ResearchObject.ObjectType.NOTE,
                "title": "Stolen",
                "content_markdown": "changed",
                "tag_names": "",
            },
        )
        self.assertEqual(response.status_code, 404)
        self.obj.refresh_from_db()
        self.assertEqual(self.obj.title, "Private experiment")

    def test_owner_can_autosave_existing_object(self):
        self.client.force_login(self.alice)
        response = self.client.post(
            reverse("research_objects:autosave", args=[self.obj.pk]),
            {
                "object_type": ResearchObject.ObjectType.EXPERIMENT,
                "title": "Autosaved",
                "content_markdown": "new body",
                "tag_names": "optimization",
                "object_version": self.obj.version,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.obj.refresh_from_db()
        self.assertEqual(self.obj.title, "Autosaved")
        self.assertEqual(self.obj.tags.get().name, "optimization")

    def test_stale_autosave_is_rejected_without_overwriting_newer_content(self):
        self.client.force_login(self.alice)
        stale_version = self.obj.version
        first = self.client.post(
            reverse("research_objects:autosave", args=[self.obj.pk]),
            {
                "object_type": ResearchObject.ObjectType.NOTE,
                "title": "First save",
                "content_markdown": "newer body",
                "tag_names": "",
                "object_version": stale_version,
            },
        )
        self.assertEqual(first.status_code, 200)
        second = self.client.post(
            reverse("research_objects:autosave", args=[self.obj.pk]),
            {
                "object_type": ResearchObject.ObjectType.NOTE,
                "title": "Stale save",
                "content_markdown": "stale body",
                "tag_names": "",
                "object_version": stale_version,
            },
        )
        self.assertEqual(second.status_code, 409)
        self.obj.refresh_from_db()
        self.assertEqual(self.obj.title, "First save")
        self.assertEqual(self.obj.content_markdown, "newer body")
        self.assertEqual(self.obj.version, stale_version + 1)

    def test_search_does_not_leak_other_users_content(self):
        self.client.force_login(self.bob)
        response = self.client.get(
            reverse("research_objects:search"),
            {"q": "Private experiment"},
        )
        self.assertEqual(list(response.context["objects"]), [])

    def test_owner_can_export_markdown(self):
        self.client.force_login(self.alice)
        response = self.client.get(
            reverse("research_objects:export", args=[self.obj.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "# Secret\nresult 42")

    def test_workspace_zip_contains_only_owned_active_content_and_attachments(self):
        Attachment.objects.create(
            owner=self.alice,
            research_object=self.obj,
            file=SimpleUploadedFile("result.txt", b"private result"),
            original_name="result.txt",
            mime_type="text/plain",
            size=14,
            sha256="1" * 64,
        )
        ResearchObject.objects.create(
            owner=self.bob,
            title="Bob secret",
            content_markdown="must not export",
        )
        self.client.force_login(self.alice)
        response = self.client.get(reverse("research_objects:workspace_export"))
        self.assertEqual(response.status_code, 200)
        payload = b"".join(response.streaming_content)
        with zipfile.ZipFile(BytesIO(payload)) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            names = archive.namelist()
            self.assertEqual(len(manifest["objects"]), 1)
            self.assertEqual(manifest["objects"][0]["title"], "Private experiment")
            self.assertTrue(any(name.endswith("result.txt") for name in names))
            self.assertNotIn(b"must not export", payload)

    def test_attachment_download_is_owner_only(self):
        attachment = Attachment.objects.create(
            owner=self.alice,
            research_object=self.obj,
            file=SimpleUploadedFile("result.txt", b"private"),
            original_name="result.txt",
            mime_type="text/plain",
            size=7,
            sha256="0" * 64,
        )
        self.client.force_login(self.bob)
        response = self.client.get(
            reverse("research_objects:attachment_download", args=[attachment.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_soft_deleted_object_disappears(self):
        self.obj.soft_delete()
        self.assertFalse(
            ResearchObject.objects.visible_to(self.alice).filter(pk=self.obj.pk).exists()
        )

    def test_dangerous_html_is_sanitized(self):
        rendered = render_markdown('<script>alert("x")</script>safe')
        self.assertNotIn("<script", rendered)
        self.assertIn("safe", rendered)

    def test_markdown_preserves_inline_and_display_math_for_mathjax(self):
        rendered = render_markdown(
            "状态空间 $\\mathcal{S}$ 与回报 $G_t$。\n\n"
            "$$V^\\pi(s)=\\mathbb{E}_\\pi[G_t \\mid S_t=s]$$"
        )
        self.assertIn(r"$\mathcal{S}$", rendered)
        self.assertIn(r"$G_t$", rendered)
        self.assertIn(r"$$V^\pi(s)=\mathbb{E}_\pi[G_t \mid S_t=s]$$", rendered)

    def test_executable_attachment_is_rejected(self):
        form = AttachmentForm(
            files={"file": SimpleUploadedFile("payload.exe", b"MZ")}
        )
        self.assertFalse(form.is_valid())

    def test_upload_is_rejected_when_user_quota_is_exceeded(self):
        profile = self.alice.profile
        profile.storage_quota_bytes = 3
        profile.save(update_fields=["storage_quota_bytes"])
        self.client.force_login(self.alice)
        response = self.client.post(
            reverse("research_objects:attachment_upload", args=[self.obj.pk]),
            {"file": SimpleUploadedFile("result.txt", b"four")},
        )
        self.assertRedirects(
            response,
            reverse("research_objects:detail", args=[self.obj.pk]),
        )
        self.assertFalse(self.obj.attachments.exists())
        profile.refresh_from_db()
        self.assertEqual(profile.storage_used_bytes, 0)

    def test_successful_upload_and_delete_update_storage_usage(self):
        self.client.force_login(self.alice)
        response = self.client.post(
            reverse("research_objects:attachment_upload", args=[self.obj.pk]),
            {"file": SimpleUploadedFile("result.txt", b"four")},
        )
        self.assertRedirects(
            response,
            reverse("research_objects:detail", args=[self.obj.pk]),
        )
        attachment = self.obj.attachments.get()
        self.alice.profile.refresh_from_db()
        self.assertEqual(self.alice.profile.storage_used_bytes, 4)
        attachment.delete()
        self.alice.profile.refresh_from_db()
        self.assertEqual(self.alice.profile.storage_used_bytes, 0)

    def test_type_template_is_prefilled(self):
        self.client.force_login(self.alice)
        response = self.client.get(
            reverse("research_objects:create"),
            {"type": ResearchObject.ObjectType.EXPERIMENT},
        )
        self.assertContains(response, "实验目的")
        self.assertContains(response, "启动命令")

    def test_relation_does_not_leak_invisible_target(self):
        hidden = ResearchObject.objects.create(
            owner=self.bob,
            title="Bob hidden target",
            content_markdown="secret",
        )
        ObjectRelation.objects.create(
            source_object=self.obj,
            target_object=hidden,
            relation_type=ObjectRelation.RelationType.RELATED,
            created_by=self.alice,
        )
        self.client.force_login(self.alice)
        response = self.client.get(
            reverse("research_objects:detail", args=[self.obj.pk])
        )
        self.assertNotContains(response, "Bob hidden target")
