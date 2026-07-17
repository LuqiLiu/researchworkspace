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
            name="SecurityAuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_type", models.CharField(choices=[("SHARE_CREATED", "Share created"), ("SHARE_UPDATED", "Share updated"), ("SHARE_REVOKED", "Share revoked"), ("PROJECT_MEMBER_ADDED", "Project member added"), ("PROJECT_MEMBER_UPDATED", "Project member updated"), ("PROJECT_MEMBER_REMOVED", "Project member removed"), ("COMMENT_DELETED", "Comment deleted")], max_length=40)),
                ("resource_type", models.CharField(max_length=80)),
                ("resource_id", models.PositiveBigIntegerField()),
                ("metadata_json", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="security_events", to=settings.AUTH_USER_MODEL)),
                ("target_user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="targeted_security_events", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ("-created_at",),
                "indexes": [models.Index(fields=["resource_type", "resource_id", "-created_at"], name="audit_secur_resourc_d76d54_idx")],
            },
        ),
    ]
