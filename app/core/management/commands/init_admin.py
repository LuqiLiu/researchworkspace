import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create or update the initial Django administrator account."

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            default=os.environ.get("DJANGO_SUPERUSER_USERNAME", "admin"),
        )
        parser.add_argument(
            "--email",
            default=os.environ.get("DJANGO_SUPERUSER_EMAIL", ""),
        )
        parser.add_argument(
            "--password",
            default=os.environ.get("DJANGO_SUPERUSER_PASSWORD"),
        )

    def handle(self, *args, **options):
        username = options["username"].strip()
        email = options["email"].strip()
        password = options["password"]

        if not username:
            raise CommandError("Administrator username cannot be empty.")
        if not password:
            raise CommandError(
                "Provide --password or set DJANGO_SUPERUSER_PASSWORD."
            )

        user_model = get_user_model()
        user, created = user_model.objects.get_or_create(
            username=username,
            defaults={"email": email},
        )
        user.email = email
        user.is_active = True
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()

        action = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(f"{action} administrator '{username}'.")
        )

