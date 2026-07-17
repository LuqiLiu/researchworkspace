import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("research_objects", "0002_stage2_project_sharing"),
    ]

    operations = [
        migrations.AddField(
            model_name="researchobject",
            name="search_text",
            field=models.TextField(blank=True, editable=False),
        ),
        migrations.CreateModel(
            name="ObjectRelation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("relation_type", models.CharField(choices=[("RELATED", "关联"), ("DERIVED_FROM", "来源于"), ("CITES", "引用"), ("SUPPORTS", "支持"), ("CONTRADICTS", "反驳"), ("VALIDATES", "验证"), ("USES", "使用"), ("PRODUCES", "产生"), ("BELONGS_TO", "属于"), ("FOLLOW_UP", "后续工作")], default="RELATED", max_length=30)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_object_relations", to=settings.AUTH_USER_MODEL)),
                ("source_object", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="outgoing_relations", to="research_objects.researchobject")),
                ("target_object", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="incoming_relations", to="research_objects.researchobject")),
            ],
            options={"ordering": ("relation_type", "target_object__title")},
        ),
        migrations.AddConstraint(
            model_name="objectrelation",
            constraint=models.UniqueConstraint(fields=("source_object", "target_object", "relation_type"), name="unique_typed_object_relation"),
        ),
        migrations.AddConstraint(
            model_name="objectrelation",
            constraint=models.CheckConstraint(condition=models.Q(("source_object", models.F("target_object")), _negated=True), name="relation_objects_must_differ"),
        ),
    ]
