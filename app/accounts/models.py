from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    display_name = models.CharField(max_length=120, blank=True)
    affiliation = models.CharField(max_length=200, blank=True)
    bio = models.TextField(blank=True)
    research_interests = models.TextField(blank=True)
    orcid = models.CharField(max_length=40, blank=True)

    def __str__(self):
        return self.display_name or self.user.get_username()


class LoginAttempt(models.Model):
    identifier = models.CharField(max_length=254, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    attempted_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-attempted_at"]
