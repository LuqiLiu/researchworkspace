from django.test import TestCase
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

    def test_home_uses_stage_zero_template(self):
        response = self.client.get(reverse("core:home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Research Workspace Lite")
        self.assertContains(response, "Stage 0")

