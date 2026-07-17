from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("research_objects", "0003_stage3_search_relations"),
    ]

    operations = [
        migrations.AddField(
            model_name="researchobject",
            name="version",
            field=models.PositiveBigIntegerField(default=1, editable=False),
        ),
    ]
