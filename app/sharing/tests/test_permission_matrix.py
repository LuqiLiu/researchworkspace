import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from app.audit.models import SecurityAuditLog
from app.comments.models import Comment
from app.projects.models import Project, ProjectMember
from app.research_objects.models import Attachment, ResearchObject
from app.sharing.models import ObjectShare


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class PermissionMatrixTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.owner = users.objects.create_user("owner", password="password")
        self.stranger = users.objects.create_user("stranger", password="password")
        self.viewer = users.objects.create_user("viewer", password="password")
        self.commenter = users.objects.create_user("commenter", password="password")
        self.editor = users.objects.create_user("editor", password="password")
        self.member = users.objects.create_user("member", password="password")
        self.project_editor = users.objects.create_user(
            "project-editor", password="password"
        )
        self.admin = users.objects.create_superuser(
            "superadmin", password="password"
        )
        self.obj = ResearchObject.objects.create(
            owner=self.owner,
            title="Shared result",
            content_markdown="private body",
        )
        self.viewer_share = ObjectShare.objects.create(
            research_object=self.obj,
            user=self.viewer,
            permission=ObjectShare.Permission.VIEWER,
            created_by=self.owner,
        )
        self.commenter_share = ObjectShare.objects.create(
            research_object=self.obj,
            user=self.commenter,
            permission=ObjectShare.Permission.COMMENTER,
            created_by=self.owner,
        )
        self.editor_share = ObjectShare.objects.create(
            research_object=self.obj,
            user=self.editor,
            permission=ObjectShare.Permission.EDITOR,
            created_by=self.owner,
        )
        self.project = Project.objects.create(
            owner=self.owner,
            name="Collaboration",
        )
        ProjectMember.objects.create(
            project=self.project,
            user=self.member,
            role=ProjectMember.Role.MEMBER,
        )
        ProjectMember.objects.create(
            project=self.project,
            user=self.project_editor,
            role=ProjectMember.Role.EDITOR,
        )
        self.project_obj = ResearchObject.objects.create(
            owner=self.owner,
            project=self.project,
            is_shared_with_project=True,
            title="Project result",
            content_markdown="project body",
        )

    def _get_as(self, user, url):
        self.client.force_login(user)
        return self.client.get(url)

    def _post_comment_as(self, user, obj):
        self.client.force_login(user)
        return self.client.post(
            reverse("comments:create", args=[obj.pk]),
            {"content": "discussion"},
        )

    def test_owner_has_full_access(self):
        self.assertEqual(
            self._get_as(
                self.owner,
                reverse("research_objects:detail", args=[self.obj.pk]),
            ).status_code,
            200,
        )
        self.assertEqual(
            self._get_as(
                self.owner,
                reverse("research_objects:edit", args=[self.obj.pk]),
            ).status_code,
            200,
        )

    def test_stranger_and_superuser_do_not_gain_private_access(self):
        url = reverse("research_objects:detail", args=[self.obj.pk])
        self.assertEqual(self._get_as(self.stranger, url).status_code, 404)
        self.assertEqual(self._get_as(self.admin, url).status_code, 404)

    def test_viewer_can_view_but_cannot_comment_or_edit(self):
        detail = reverse("research_objects:detail", args=[self.obj.pk])
        edit = reverse("research_objects:edit", args=[self.obj.pk])
        self.assertEqual(self._get_as(self.viewer, detail).status_code, 200)
        self.assertEqual(self._get_as(self.viewer, edit).status_code, 404)
        self.assertEqual(
            self._post_comment_as(self.viewer, self.obj).status_code,
            404,
        )

    def test_commenter_can_comment_but_cannot_edit(self):
        response = self._post_comment_as(self.commenter, self.obj)
        self.assertRedirects(
            response,
            reverse("research_objects:detail", args=[self.obj.pk]),
        )
        self.assertTrue(
            Comment.objects.filter(
                research_object=self.obj,
                author=self.commenter,
            ).exists()
        )
        self.assertEqual(
            self._get_as(
                self.commenter,
                reverse("research_objects:edit", args=[self.obj.pk]),
            ).status_code,
            404,
        )

    def test_editor_can_edit_but_cannot_manage_shares(self):
        self.client.force_login(self.editor)
        response = self.client.post(
            reverse("research_objects:edit", args=[self.obj.pk]),
            {
                "object_type": ResearchObject.ObjectType.NOTE,
                "title": "Edited by collaborator",
                "content_markdown": "updated",
                "object_version": self.obj.version,
            },
        )
        self.assertRedirects(
            response,
            reverse("research_objects:detail", args=[self.obj.pk]),
        )
        self.obj.refresh_from_db()
        self.assertEqual(self.obj.title, "Edited by collaborator")

        response = self.client.post(
            reverse("sharing:revoke", args=[self.viewer_share.pk])
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            ObjectShare.objects.filter(pk=self.viewer_share.pk).exists()
        )

    def test_project_member_comments_and_project_editor_edits(self):
        self.assertRedirects(
            self._post_comment_as(self.member, self.project_obj),
            reverse("research_objects:detail", args=[self.project_obj.pk]),
        )
        self.assertEqual(
            self._get_as(
                self.member,
                reverse("research_objects:edit", args=[self.project_obj.pk]),
            ).status_code,
            404,
        )
        self.assertEqual(
            self._get_as(
                self.project_editor,
                reverse("research_objects:edit", args=[self.project_obj.pk]),
            ).status_code,
            200,
        )

    def test_project_members_only_see_explicit_project_shares(self):
        unshared = ResearchObject.objects.create(
            owner=self.owner,
            project=self.project,
            title="Not shared to project",
            content_markdown="hidden",
        )
        self.assertEqual(
            self._get_as(
                self.member,
                reverse("research_objects:detail", args=[unshared.pk]),
            ).status_code,
            404,
        )

    def test_direct_share_revocation_is_immediate_and_audited(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("sharing:revoke", args=[self.viewer_share.pk])
        )
        self.assertRedirects(
            response,
            reverse("research_objects:detail", args=[self.obj.pk]),
        )
        self.assertEqual(
            self._get_as(
                self.viewer,
                reverse("research_objects:detail", args=[self.obj.pk]),
            ).status_code,
            404,
        )
        self.assertTrue(
            SecurityAuditLog.objects.filter(
                event_type=SecurityAuditLog.EventType.SHARE_REVOKED,
                resource_id=self.obj.pk,
                target_user=self.viewer,
            ).exists()
        )

    def test_owner_can_create_and_update_share_through_views(self):
        recipient = get_user_model().objects.create_user(
            "new-recipient",
            password="password",
        )
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("sharing:create", args=[self.obj.pk]),
            {
                "user": recipient.pk,
                "permission": ObjectShare.Permission.VIEWER,
                "include_attachments": "",
            },
        )
        self.assertRedirects(
            response,
            reverse("research_objects:detail", args=[self.obj.pk]),
        )
        share = ObjectShare.objects.get(
            research_object=self.obj,
            user=recipient,
        )
        self.obj.refresh_from_db()
        self.assertEqual(self.obj.status, ResearchObject.Status.SHARED)
        self.assertTrue(
            SecurityAuditLog.objects.filter(
                event_type=SecurityAuditLog.EventType.SHARE_CREATED,
                target_user=recipient,
            ).exists()
        )

        response = self.client.post(
            reverse("sharing:update", args=[share.pk]),
            {
                "permission": ObjectShare.Permission.EDITOR,
                "include_attachments": "on",
            },
        )
        self.assertRedirects(
            response,
            reverse("research_objects:detail", args=[self.obj.pk]),
        )
        share.refresh_from_db()
        self.assertEqual(share.permission, ObjectShare.Permission.EDITOR)
        self.assertTrue(share.include_attachments)

    def test_project_member_removal_revokes_access_immediately(self):
        membership = ProjectMember.objects.get(
            project=self.project,
            user=self.member,
        )
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("projects:member_remove", args=[membership.pk])
        )
        self.assertRedirects(
            response,
            reverse("projects:detail", args=[self.project.pk]),
        )
        self.assertEqual(
            self._get_as(
                self.member,
                reverse("research_objects:detail", args=[self.project_obj.pk]),
            ).status_code,
            404,
        )

    def test_attachment_requires_separate_permission(self):
        attachment = Attachment.objects.create(
            owner=self.owner,
            research_object=self.obj,
            file=SimpleUploadedFile("private.pdf", b"pdf"),
            original_name="private.pdf",
            mime_type="application/pdf",
            size=3,
            sha256="0" * 64,
        )
        url = reverse(
            "research_objects:attachment_download",
            args=[attachment.pk],
        )
        self.assertEqual(self._get_as(self.viewer, url).status_code, 404)
        self.viewer_share.include_attachments = True
        self.viewer_share.save(update_fields=["include_attachments"])
        response = self._get_as(self.viewer, url)
        self.assertEqual(response.status_code, 200)

    def test_revoked_user_cannot_search_or_read_comments(self):
        comment = Comment.objects.create(
            research_object=self.obj,
            author=self.commenter,
            content="private discussion",
        )
        self.commenter_share.delete()
        self.client.force_login(self.commenter)
        response = self.client.get(
            reverse("research_objects:search"),
            {"q": "Shared result"},
        )
        self.assertEqual(list(response.context["objects"]), [])
        self.assertEqual(
            self.client.get(
                reverse("research_objects:detail", args=[self.obj.pk])
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                reverse("comments:delete", args=[comment.pk])
            ).status_code,
            404,
        )

    def test_comment_reply_is_linked_to_parent(self):
        parent = Comment.objects.create(
            research_object=self.obj,
            author=self.owner,
            content="question",
        )
        self.client.force_login(self.commenter)
        response = self.client.post(
            reverse("comments:create", args=[self.obj.pk]),
            {"content": "answer", "parent": parent.pk},
        )
        self.assertRedirects(
            response,
            reverse("research_objects:detail", args=[self.obj.pk]),
        )
        reply = Comment.objects.get(content="answer")
        self.assertEqual(reply.parent, parent)

    def test_project_owner_can_add_member_through_view(self):
        newcomer = get_user_model().objects.create_user(
            "project-newcomer",
            password="password",
        )
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("projects:member_add", args=[self.project.pk]),
            {"user": newcomer.pk, "role": ProjectMember.Role.MEMBER},
        )
        self.assertRedirects(
            response,
            reverse("projects:detail", args=[self.project.pk]),
        )
        self.assertTrue(
            ProjectMember.objects.filter(
                project=self.project,
                user=newcomer,
            ).exists()
        )
        self.assertEqual(
            self._get_as(
                newcomer,
                reverse(
                    "research_objects:detail",
                    args=[self.project_obj.pk],
                ),
            ).status_code,
            200,
        )

    def test_owner_can_review_every_outgoing_recipient(self):
        response = self._get_as(self.owner, reverse("sharing:sent_shares"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Shared result")
        self.assertContains(response, "Project result")
        self.assertContains(response, "viewer")
        self.assertContains(response, "commenter")
        self.assertContains(response, "editor")
        self.assertContains(response, "member")
        self.assertContains(response, "project-editor")
        self.assertContains(response, "直接分享")
        self.assertContains(response, "项目：Collaboration")

    def test_outgoing_roster_merges_access_routes_and_effective_permission(self):
        ObjectShare.objects.create(
            research_object=self.project_obj,
            user=self.member,
            permission=ObjectShare.Permission.EDITOR,
            include_attachments=True,
            created_by=self.owner,
        )

        response = self._get_as(self.owner, reverse("sharing:sent_shares"))
        project_object = next(
            obj
            for obj in response.context["objects"]
            if obj.pk == self.project_obj.pk
        )
        member_rows = [
            recipient
            for recipient in project_object.access_recipients
            if recipient["user"] == self.member
        ]

        self.assertEqual(len(member_rows), 1)
        self.assertEqual(member_rows[0]["permission_label"], "查看、评论和编辑")
        self.assertTrue(member_rows[0]["include_attachments"])
        self.assertEqual(
            member_rows[0]["sources"],
            ["直接分享", "项目：Collaboration"],
        )

    def test_owner_detail_shows_roster_but_recipient_detail_does_not(self):
        url = reverse("research_objects:detail", args=[self.obj.pk])
        owner_response = self._get_as(self.owner, url)
        viewer_response = self._get_as(self.viewer, url)

        self.assertContains(owner_response, "实际访问成员")
        self.assertContains(owner_response, "commenter")
        self.assertNotContains(viewer_response, "实际访问成员")
        self.assertNotContains(viewer_response, "commenter")

    def test_outgoing_overview_does_not_expose_another_owners_shares(self):
        stranger_object = ResearchObject.objects.create(
            owner=self.stranger,
            title="Another owner's private share",
        )
        ObjectShare.objects.create(
            research_object=stranger_object,
            user=self.viewer,
            created_by=self.stranger,
        )

        response = self._get_as(self.owner, reverse("sharing:sent_shares"))

        self.assertNotContains(response, "Another owner's private share")
