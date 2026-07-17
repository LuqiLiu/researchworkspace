import json
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.contrib.auth import get_user_model
from django.test import TestCase

from app.audit.models import SecurityAuditLog
from app.research_objects.models import ResearchObject


class OperationsCommandTests(TestCase):
    @patch("app.core.management.commands.check_storage.shutil.disk_usage")
    def test_storage_check_reports_machine_readable_capacity(self, disk_usage):
        disk_usage.return_value = SimpleNamespace(
            total=10 * 1024**3,
            used=4 * 1024**3,
            free=6 * 1024**3,
        )
        output = StringIO()

        call_command("check_storage", minimum_free_mb=1024, json=True, stdout=output)

        report = json.loads(output.getvalue())
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["free_bytes"], 6 * 1024**3)

    @patch("app.core.management.commands.check_storage.shutil.disk_usage")
    def test_storage_check_fails_below_threshold(self, disk_usage):
        disk_usage.return_value = SimpleNamespace(
            total=10 * 1024**3,
            used=9 * 1024**3,
            free=512 * 1024**2,
        )

        with self.assertRaises(CommandError):
            call_command(
                "check_storage",
                minimum_free_mb=1024,
                json=True,
                stdout=StringIO(),
                stderr=StringIO(),
            )

    def test_system_operation_event_is_recorded(self):
        call_command(
            "record_system_event",
            SecurityAuditLog.EventType.BACKUP_CREATED,
            detail="daily/verified",
        )

        event = SecurityAuditLog.objects.get(
            event_type=SecurityAuditLog.EventType.BACKUP_CREATED
        )
        self.assertEqual(event.resource_type, "system")
        self.assertEqual(event.metadata_json, {"detail": "daily/verified"})

    def test_demo_seed_is_private_ordinary_and_idempotent(self):
        for _ in range(2):
            call_command(
                "seed_demo",
                username="demo-researcher",
                email="demo@example.com",
                password="demo-test-password",
                stdout=StringIO(),
            )

        user = get_user_model().objects.get(username="demo-researcher")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(ResearchObject.objects.filter(owner=user).count(), 3)
        self.assertFalse(
            ResearchObject.objects.filter(owner=user).exclude(
                status=ResearchObject.Status.PRIVATE
            ).exists()
        )
