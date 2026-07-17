import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("research_objects", "0002_stage2_project_sharing"),
    ]

    operations = [
        migrations.CreateModel(
            name="ObjectShare",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("permission", models.CharField(choices=[("VIEWER", "查看"), ("COMMENTER", "查看和评论"), ("EDITOR", "查看、评论和编辑")], max_length=20)),
                ("include_attachments", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_object_shares", to=settings.AUTH_USER_MODEL)),
                ("research_object", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="direct_shares", to="research_objects.researchobject")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="received_object_shares", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("user__username",)},
        ),
        migrations.AddConstraint(
            model_name="objectshare",
            constraint=models.UniqueConstraint(fields=("research_object", "user"), name="unique_object_share_user"),
        ),
    ]
