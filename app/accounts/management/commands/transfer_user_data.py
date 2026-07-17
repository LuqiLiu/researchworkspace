from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from app.accounts.services import transfer_user_data


class Command(BaseCommand):
    help = "Transfer all V1-owned data from a deactivated user to an active user."

    def add_arguments(self, parser):
        parser.add_argument("source_username")
        parser.add_argument("target_username")
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Confirm the irreversible ownership transfer.",
        )

    def handle(self, *args, **options):
        if not options["yes"]:
            raise CommandError("Refusing transfer without --yes confirmation.")

        User = get_user_model()
        try:
            source = User.objects.get(username=options["source_username"])
            target = User.objects.get(username=options["target_username"])
        except User.DoesNotExist as exc:
            raise CommandError("Source or target user does not exist.") from exc

        try:
            counts = transfer_user_data(
                source_user=source,
                target_user=target,
            )
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        summary = ", ".join(f"{key}={value}" for key, value in counts.items())
        self.stdout.write(self.style.SUCCESS(f"Ownership transferred: {summary}"))
