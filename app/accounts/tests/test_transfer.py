from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase

from app.audit.models import SecurityAuditLog
from app.projects.models import Project, ProjectMember
from app.publications.models import PublicationSnapshot
from app.research_objects.models import Attachment, ResearchObject, Tag

from app.accounts.services import transfer_user_data


class UserDataTransferTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.source = User.objects.create_user("former", password="password")
        self.target = User.objects.create_user("successor", password="password")
        self.source.is_active = False
        self.source.save(update_fields=["is_active"])

        self.project = Project.objects.create(owner=self.source, name="Lab project")
        ProjectMember.objects.create(project=self.project, user=self.target)
        self.research_object = ResearchObject.objects.create(
            owner=self.source,
            project=self.project,
            title="Transferred result",
            content_markdown="Evidence",
        )
        self.source_tag = Tag.objects.create(owner=self.source, name="Methods")
        self.target_tag = Tag.objects.create(owner=self.target, name="methods")
        self.research_object.tags.add(self.source_tag)
        self.attachment = Attachment.objects.create(
            owner=self.source,
            research_object=self.research_object,
            file=SimpleUploadedFile("result.txt", b"result"),
            original_name="result.txt",
            mime_type="text/plain",
            size=6,
            sha256="0" * 64,
        )
        self.snapshot = PublicationSnapshot.objects.create(
            source_object=self.research_object,
            owner=self.source,
            public_slug="result",
            title="Transferred result",
        )
        other_object = ResearchObject.objects.create(
            owner=self.target,
            title="Existing result",
            content_markdown="Existing",
        )
        PublicationSnapshot.objects.create(
            source_object=other_object,
            owner=self.target,
            public_slug="result",
            title="Existing result",
        )
        self.source.profile.storage_used_bytes = 6
        self.source.profile.public_enabled = True
        self.source.profile.save(
            update_fields=["storage_used_bytes", "public_enabled"]
        )

    def test_transfer_moves_owned_data_merges_tags_and_records_audit(self):
        counts = transfer_user_data(
            source_user=self.source,
            target_user=self.target,
            actor=self.target,
        )

        self.assertEqual(counts["research_objects"], 1)
        self.research_object.refresh_from_db()
        self.attachment.refresh_from_db()
        self.project.refresh_from_db()
        self.snapshot.refresh_from_db()
        self.source.profile.refresh_from_db()
        self.target.profile.refresh_from_db()
        self.assertEqual(self.research_object.owner, self.target)
        self.assertEqual(self.attachment.owner, self.target)
        self.assertEqual(self.project.owner, self.target)
        self.assertFalse(
            ProjectMember.objects.filter(
                project=self.project,
                user=self.target,
            ).exists()
        )
        self.assertEqual(self.snapshot.owner, self.target)
        self.assertEqual(self.snapshot.public_slug, "result-2")
        self.assertEqual(
            list(self.research_object.tags.values_list("pk", flat=True)),
            [self.target_tag.pk],
        )
        self.assertEqual(self.source.profile.storage_used_bytes, 0)
        self.assertFalse(self.source.profile.public_enabled)
        self.assertEqual(self.target.profile.storage_used_bytes, 6)
        self.assertTrue(
            SecurityAuditLog.objects.filter(
                event_type=SecurityAuditLog.EventType.OWNERSHIP_TRANSFERRED,
                resource_id=self.source.pk,
                target_user=self.target,
            ).exists()
        )

    def test_active_source_is_rejected(self):
        self.source.is_active = True
        self.source.save(update_fields=["is_active"])
        with self.assertRaisesMessage(
            ValidationError,
            "数据交接前必须先停用源账号",
        ):
            transfer_user_data(
                source_user=self.source,
                target_user=self.target,
            )

    def test_management_command_requires_confirmation(self):
        with self.assertRaisesMessage(Exception, "--yes"):
            call_command("transfer_user_data", "former", "successor")
