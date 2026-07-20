from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("research_objects", "0004_researchobject_version"),
    ]

    operations = [
        migrations.AddField(
            model_name="researchobject",
            name="is_shared_with_team",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="researchobject",
            name="share_team_attachments",
            field=models.BooleanField(default=False),
        ),
    ]
