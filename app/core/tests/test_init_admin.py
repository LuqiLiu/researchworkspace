from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase


class InitAdminCommandTests(TestCase):
    def test_command_creates_and_updates_admin_idempotently(self):
        call_command(
            "init_admin",
            username="admin",
            email="first@example.com",
            password="first-password",
        )

        user = get_user_model().objects.get(username="admin")
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_active)
        self.assertEqual(user.email, "first@example.com")
        self.assertTrue(user.check_password("first-password"))

        call_command(
            "init_admin",
            username="admin",
            email="second@example.com",
            password="second-password",
        )

        self.assertEqual(get_user_model().objects.filter(username="admin").count(), 1)
        user.refresh_from_db()
        self.assertEqual(user.email, "second@example.com")
        self.assertTrue(user.check_password("second-password"))

