import app.research_objects.models
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ResearchObject",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("object_type", models.CharField(choices=[("NOTE", "普通笔记"), ("PAPER", "文献"), ("IDEA", "科研想法"), ("EXPERIMENT", "实验记录"), ("ISSUE", "问题与踩坑"), ("WRITING", "写作素材"), ("RESOURCE", "资源索引")], default="NOTE", max_length=20)),
                ("title", models.CharField(max_length=240)),
                ("content_markdown", models.TextField()),
                ("content_plain_text", models.TextField(blank=True, editable=False)),
                ("metadata_json", models.JSONField(blank=True, default=dict)),
                ("status", models.CharField(choices=[("PRIVATE", "仅自己")], default="PRIVATE", editable=False, max_length=20)),
                ("is_favorite", models.BooleanField(default=False)),
                ("is_archived", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="research_objects", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ("-updated_at",),
                "indexes": [
                    models.Index(fields=["owner", "deleted_at", "-updated_at"], name="research_ob_owner_i_e186fe_idx"),
                    models.Index(fields=["owner", "is_archived"], name="research_ob_owner_i_58eb42_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="Attachment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("file", models.FileField(upload_to=app.research_objects.models.attachment_upload_path)),
                ("original_name", models.CharField(max_length=255)),
                ("mime_type", models.CharField(blank=True, max_length=120)),
                ("size", models.PositiveBigIntegerField()),
                ("sha256", models.CharField(max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attachments", to=settings.AUTH_USER_MODEL)),
                ("research_object", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attachments", to="research_objects.researchobject")),
            ],
        ),
        migrations.CreateModel(
            name="Tag",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80)),
                ("normalized_name", models.CharField(editable=False, max_length=80)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="research_tags", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("name",)},
        ),
        migrations.AddField(
            model_name="researchobject",
            name="tags",
            field=models.ManyToManyField(blank=True, related_name="research_objects", to="research_objects.tag"),
        ),
        migrations.AddConstraint(
            model_name="tag",
            constraint=models.UniqueConstraint(fields=("owner", "normalized_name"), name="unique_tag_per_owner"),
        ),
    ]
