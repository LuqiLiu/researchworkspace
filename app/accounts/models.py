import uuid
from pathlib import Path

from django.conf import settings
from django.db import models
from django.utils.text import slugify


def profile_avatar_upload_path(instance, filename):
    suffix = Path(filename).suffix.lower()
    return f"profiles/{instance.user_id}/{uuid.uuid4().hex}{suffix}"


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    display_name = models.CharField(max_length=120, blank=True)
    avatar = models.FileField(upload_to=profile_avatar_upload_path, blank=True)
    affiliation = models.CharField(max_length=200, blank=True)
    position = models.CharField(max_length=120, blank=True)
    bio = models.TextField(blank=True)
    research_interests = models.TextField(blank=True)
    orcid = models.CharField(max_length=40, blank=True)
    google_scholar_url = models.URLField(blank=True)
    github_url = models.URLField(blank=True)
    contact_email = models.EmailField(blank=True)
    public_enabled = models.BooleanField(default=False)
    public_slug = models.SlugField(
        max_length=150,
        allow_unicode=True,
        unique=True,
        null=True,
        blank=True,
    )

    def save(self, *args, **kwargs):
        if not self.public_slug:
            base = (
                slugify(self.user.get_username(), allow_unicode=True)
                or f"researcher-{self.user_id}"
            )
            candidate = base[:140]
            suffix = 2
            queryset = type(self).objects.exclude(pk=self.pk)
            while queryset.filter(public_slug=candidate).exists():
                candidate = f"{base[:135]}-{suffix}"
                suffix += 1
            self.public_slug = candidate
        super().save(*args, **kwargs)

    def __str__(self):
        return self.display_name or self.user.get_username()


class LoginAttempt(models.Model):
    identifier = models.CharField(max_length=254, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    attempted_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-attempted_at"]
