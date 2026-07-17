import json
import os
import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


def directory_size(path):
    total = 0
    if not path.exists():
        return total
    for root, _, files in os.walk(path):
        for filename in files:
            file_path = Path(root) / filename
            try:
                total += file_path.stat().st_size
            except FileNotFoundError:
                continue
    return total


def existing_probe_path(path):
    probe = path
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    return probe


class Command(BaseCommand):
    help = "Check free disk capacity for private media storage."

    def add_arguments(self, parser):
        parser.add_argument(
            "--minimum-free-mb",
            type=int,
            default=int(os.environ.get("MINIMUM_FREE_DISK_MB", "1024")),
        )
        parser.add_argument("--json", action="store_true")

    def handle(self, *args, **options):
        media_root = Path(settings.MEDIA_ROOT)
        usage = shutil.disk_usage(existing_probe_path(media_root))
        result = {
            "status": "ok",
            "media_bytes": directory_size(media_root),
            "free_bytes": usage.free,
            "total_bytes": usage.total,
            "minimum_free_bytes": options["minimum_free_mb"] * 1024 * 1024,
        }
        if usage.free < result["minimum_free_bytes"]:
            result["status"] = "critical"
        output = json.dumps(result, separators=(",", ":"))
        if options["json"]:
            self.stdout.write(output)
        else:
            self.stdout.write(
                f"Storage {result['status']}: "
                f"{usage.free // (1024 * 1024)} MB free; "
                f"media uses {result['media_bytes'] // (1024 * 1024)} MB."
            )
        if result["status"] == "critical":
            raise CommandError(output)
