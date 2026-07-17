from django.core.management.base import BaseCommand

from app.audit.models import SecurityAuditLog


class Command(BaseCommand):
    help = "Record a backup or restore security event from an operations script."

    allowed_events = {
        SecurityAuditLog.EventType.BACKUP_CREATED,
        SecurityAuditLog.EventType.RESTORE_COMPLETED,
    }

    def add_arguments(self, parser):
        parser.add_argument("event", choices=sorted(self.allowed_events))
        parser.add_argument("--detail", default="")

    def handle(self, *args, **options):
        event = SecurityAuditLog.objects.create(
            event_type=options["event"],
            resource_type="system",
            resource_id=0,
            metadata_json={"detail": options["detail"]},
        )
        self.stdout.write(self.style.SUCCESS(f"Recorded system event {event.pk}."))
