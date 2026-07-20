import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from app.comments.models import Comment
from app.projects.models import Project
from app.research_objects.models import Attachment, ResearchObject, Tag
from app.sharing.services import can_view, visible_objects


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class TeamLibraryTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.alice = users.objects.create_user("alice", password="password")
        self.bob = users.objects.create_user("bob", password="password")
        self.private = ResearchObject.objects.create(
            owner=self.alice,
            object_type=ResearchObject.ObjectType.IDEA,
            title="Private hypothesis",
            content_markdown="must stay private",
        )
        self.project = Project.objects.create(
            owner=self.alice,
            name="Team robotics",
        )
        self.shared = ResearchObject.objects.create(
            owner=self.alice,
            object_type=ResearchObject.ObjectType.PAPER,
            title="Shared manipulation paper",
            content_markdown="policy learning notes",
            project=self.project,
            is_shared_with_team=True,
        )
        self.tag = Tag.objects.create(owner=self.alice, name="robotics")
        self.shared.tags.add(self.tag)

    def test_library_requires_login_and_never_lists_private_content(self):
        url = reverse("community:library")
        self.assertEqual(self.client.get(url).status_code, 302)

        self.client.force_login(self.bob)
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Shared manipulation paper")
        self.assertNotContains(response, "Private hypothesis")
        self.assertContains(response, "alice")

        explicit_shares = self.client.get(reverse("sharing:shared_with_me"))
        self.assertNotContains(explicit_shares, "Shared manipulation paper")

    def test_team_member_can_view_and_comment_but_cannot_edit(self):
        self.client.force_login(self.bob)

        detail = self.client.get(
            reverse("research_objects:detail", args=[self.shared.pk])
        )
        edit = self.client.get(
            reverse("research_objects:edit", args=[self.shared.pk])
        )
        comment = self.client.post(
            reverse("comments:create", args=[self.shared.pk]),
            {"content": "Useful team note"},
        )

        self.assertEqual(detail.status_code, 200)
        self.assertEqual(edit.status_code, 404)
        self.assertRedirects(
            comment,
            reverse("research_objects:detail", args=[self.shared.pk]),
        )
        self.assertTrue(
            Comment.objects.filter(
                research_object=self.shared,
                author=self.bob,
                content="Useful team note",
            ).exists()
        )

    def test_team_attachment_access_is_separately_opt_in(self):
        attachment = Attachment.objects.create(
            owner=self.alice,
            research_object=self.shared,
            file=SimpleUploadedFile("paper.pdf", b"pdf"),
            original_name="paper.pdf",
            mime_type="application/pdf",
            size=3,
            sha256="a" * 64,
        )
        url = reverse(
            "research_objects:attachment_download",
            args=[attachment.pk],
        )
        self.client.force_login(self.bob)

        self.assertEqual(self.client.get(url).status_code, 404)
        self.shared.share_team_attachments = True
        self.shared.save(update_fields=["share_team_attachments", "updated_at"])
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_library_filters_by_type_project_author_tag_and_query(self):
        ResearchObject.objects.create(
            owner=self.bob,
            object_type=ResearchObject.ObjectType.RESOURCE,
            title="Shared simulator index",
            content_markdown="simulation resources",
            is_shared_with_team=True,
        )
        self.client.force_login(self.bob)
        url = reverse("community:library")

        filters = [
            {"type": ResearchObject.ObjectType.PAPER},
            {"project": self.project.pk},
            {"author": self.alice.pk},
            {"tag": "robotics"},
            {"q": "policy learning"},
        ]
        for params in filters:
            response = self.client.get(url, params)
            self.assertContains(response, "Shared manipulation paper")
            self.assertNotContains(response, "Shared simulator index")

    def test_new_type_defaults_are_safe_and_predictable(self):
        self.client.force_login(self.alice)

        paper = self.client.get(
            reverse("research_objects:create"),
            {"type": ResearchObject.ObjectType.PAPER},
        )
        idea = self.client.get(
            reverse("research_objects:create"),
            {"type": ResearchObject.ObjectType.IDEA},
        )

        self.assertTrue(paper.context["form"]["is_shared_with_team"].value())
        self.assertFalse(idea.context["form"]["is_shared_with_team"].value())

    def test_owner_can_explicitly_create_private_paper(self):
        self.client.force_login(self.alice)
        response = self.client.post(
            reverse("research_objects:create"),
            {
                "object_type": ResearchObject.ObjectType.PAPER,
                "title": "Deliberately private paper",
                "content_markdown": "private notes",
                "tag_names": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        created = ResearchObject.objects.get(title="Deliberately private paper")
        self.assertFalse(created.is_shared_with_team)
        self.assertEqual(created.status, ResearchObject.Status.PRIVATE)

    def test_owner_can_share_and_withdraw_an_existing_record(self):
        self.client.force_login(self.alice)
        edit_url = reverse("research_objects:edit", args=[self.private.pk])
        share_response = self.client.post(
            edit_url,
            {
                "object_type": ResearchObject.ObjectType.IDEA,
                "title": self.private.title,
                "content_markdown": self.private.content_markdown,
                "tag_names": "",
                "is_shared_with_team": "on",
                "object_version": self.private.version,
            },
        )
        self.assertRedirects(
            share_response,
            reverse("research_objects:detail", args=[self.private.pk]),
        )
        self.private.refresh_from_db()
        self.assertTrue(self.private.is_shared_with_team)
        self.assertEqual(self.private.status, ResearchObject.Status.SHARED)

        self.client.force_login(self.bob)
        detail_url = reverse("research_objects:detail", args=[self.private.pk])
        self.assertEqual(self.client.get(detail_url).status_code, 200)

        self.client.force_login(self.alice)
        withdraw_response = self.client.post(
            edit_url,
            {
                "object_type": ResearchObject.ObjectType.IDEA,
                "title": self.private.title,
                "content_markdown": self.private.content_markdown,
                "tag_names": "",
                "object_version": self.private.version,
            },
        )
        self.assertRedirects(withdraw_response, detail_url)
        self.private.refresh_from_db()
        self.assertFalse(self.private.is_shared_with_team)
        self.assertEqual(self.private.status, ResearchObject.Status.PRIVATE)

        self.client.force_login(self.bob)
        self.assertEqual(self.client.get(detail_url).status_code, 404)

    def test_inactive_account_does_not_gain_team_access(self):
        inactive = get_user_model().objects.create_user(
            "inactive",
            password="password",
            is_active=False,
        )

        self.assertFalse(can_view(inactive, self.shared))
        self.assertEqual(list(visible_objects(inactive)), [])
