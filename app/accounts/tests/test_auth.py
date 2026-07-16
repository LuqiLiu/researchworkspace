from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class AccountTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="alice",
            email="alice@example.com",
            password="correct-password",
        )

    def test_user_can_login_with_email(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "alice@example.com", "password": "correct-password"},
        )
        self.assertRedirects(response, reverse("research_objects:list"))

    def test_profile_is_created_and_can_be_updated(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("accounts:profile"),
            {
                "display_name": "Alice",
                "email": "new@example.com",
                "affiliation": "Lab",
                "bio": "",
                "research_interests": "Optimization",
                "orcid": "",
            },
        )
        self.assertRedirects(response, reverse("accounts:profile"))
        self.user.refresh_from_db()
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.email, "new@example.com")
        self.assertEqual(self.user.profile.display_name, "Alice")

    def test_login_is_rate_limited_after_repeated_failures(self):
        url = reverse("accounts:login")
        for _ in range(5):
            self.client.post(
                url,
                {"username": "alice", "password": "wrong"},
                REMOTE_ADDR="127.0.0.9",
            )
        response = self.client.post(
            url,
            {"username": "alice", "password": "wrong"},
            REMOTE_ADDR="127.0.0.9",
        )
        self.assertEqual(response.status_code, 429)
