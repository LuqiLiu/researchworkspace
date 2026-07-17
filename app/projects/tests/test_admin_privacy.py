from django.contrib import admin
from django.test import SimpleTestCase

from app.projects.models import Project, ProjectMember


class ProjectAdminPrivacyTests(SimpleTestCase):
    def test_private_project_models_are_not_registered_in_admin(self):
        self.assertNotIn(Project, admin.site._registry)
        self.assertNotIn(ProjectMember, admin.site._registry)
