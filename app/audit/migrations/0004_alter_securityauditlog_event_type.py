from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0003_alter_securityauditlog_event_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="securityauditlog",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("SHARE_CREATED", "Share created"),
                    ("SHARE_UPDATED", "Share updated"),
                    ("SHARE_REVOKED", "Share revoked"),
                    ("PROJECT_MEMBER_ADDED", "Project member added"),
                    ("PROJECT_MEMBER_UPDATED", "Project member updated"),
                    ("PROJECT_MEMBER_REMOVED", "Project member removed"),
                    ("COMMENT_DELETED", "Comment deleted"),
                    ("PUBLICATION_PUBLISHED", "Publication published"),
                    ("PUBLICATION_WITHDRAWN", "Publication withdrawn"),
                    ("BACKUP_CREATED", "Backup created"),
                    ("RESTORE_COMPLETED", "Restore completed"),
                    (
                        "OWNERSHIP_TRANSFERRED",
                        "User data ownership transferred",
                    ),
                ],
                max_length=40,
            ),
        ),
    ]
