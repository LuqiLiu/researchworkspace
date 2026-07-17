import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0001_initial"),
        ("research_objects", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="researchobject",
            name="is_shared_with_project",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="researchobject",
            name="project",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="research_objects", to="projects.project"),
        ),
        migrations.AddField(
            model_name="researchobject",
            name="share_project_attachments",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="researchobject",
            name="status",
            field=models.CharField(choices=[("PRIVATE", "仅自己"), ("SHARED", "已分享")], default="PRIVATE", editable=False, max_length=20),
        ),
    ]
