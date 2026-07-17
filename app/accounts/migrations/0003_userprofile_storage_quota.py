from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_userprofile_avatar_userprofile_contact_email_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="storage_quota_bytes",
            field=models.PositiveBigIntegerField(default=536870912),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="storage_used_bytes",
            field=models.PositiveBigIntegerField(default=0, editable=False),
        ),
    ]
