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
            name="LoginAttempt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("identifier", models.CharField(db_index=True, max_length=254)),
                ("ip_address", models.GenericIPAddressField(blank=True, db_index=True, null=True)),
                ("attempted_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={"ordering": ["-attempted_at"]},
        ),
        migrations.CreateModel(
            name="UserProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("display_name", models.CharField(blank=True, max_length=120)),
                ("affiliation", models.CharField(blank=True, max_length=200)),
                ("bio", models.TextField(blank=True)),
                ("research_interests", models.TextField(blank=True)),
                ("orcid", models.CharField(blank=True, max_length=40)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="profile", to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
