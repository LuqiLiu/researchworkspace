from django.db import migrations
from django.db.models import Sum


def backfill_storage_usage(apps, schema_editor):
    UserProfile = apps.get_model("accounts", "UserProfile")
    Attachment = apps.get_model("research_objects", "Attachment")
    PublishedAttachment = apps.get_model("publications", "PublishedAttachment")

    usage = {}
    for row in Attachment.objects.values("owner_id").annotate(total=Sum("size")):
        usage[row["owner_id"]] = row["total"] or 0
    for row in PublishedAttachment.objects.values("snapshot__owner_id").annotate(
        total=Sum("size")
    ):
        owner_id = row["snapshot__owner_id"]
        usage[owner_id] = usage.get(owner_id, 0) + (row["total"] or 0)

    UserProfile.objects.update(storage_used_bytes=0)
    for owner_id, total in usage.items():
        UserProfile.objects.filter(user_id=owner_id).update(storage_used_bytes=total)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_userprofile_storage_quota"),
        ("publications", "0001_initial"),
        ("research_objects", "0004_researchobject_version"),
    ]

    operations = [
        migrations.RunPython(backfill_storage_usage, migrations.RunPython.noop),
    ]
