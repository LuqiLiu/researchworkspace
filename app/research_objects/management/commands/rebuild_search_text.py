from django.core.management.base import BaseCommand

from app.research_objects.models import ResearchObject


class Command(BaseCommand):
    help = "Rebuild normalized search text for all research objects."

    def handle(self, *args, **options):
        updated = 0
        for obj in ResearchObject.objects.iterator(chunk_size=200):
            obj.save(update_fields=["content_plain_text", "search_text", "updated_at"])
            updated += 1
        self.stdout.write(self.style.SUCCESS(f"Rebuilt {updated} objects."))
