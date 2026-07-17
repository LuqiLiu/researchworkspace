from django.test import TestCase, override_settings
from django.urls import reverse


class HealthViewTests(TestCase):
    def test_liveness_endpoint(self):
        response = self.client.get(reverse("core:liveness"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "service": "web"})
        self.assertEqual(response["Cache-Control"], "max-age=0, no-cache, no-store, must-revalidate, private")

    def test_readiness_endpoint(self):
        response = self.client.get(reverse("core:readiness"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok"})

    @override_settings(SECURE_SSL_REDIRECT=True)
    def test_readiness_healthcheck_can_mark_internal_request_as_secure(self):
        response = self.client.get(
            reverse("core:readiness"),
            HTTP_X_FORWARDED_PROTO="https",
        )
        self.assertEqual(response.status_code, 200)

    def test_home_links_to_login(self):
        response = self.client.get(reverse("core:home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Research Workspace Lite")
        self.assertContains(response, "进入工作台")
