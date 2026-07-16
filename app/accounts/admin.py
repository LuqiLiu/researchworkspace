from django.contrib import admin

from .models import LoginAttempt, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "display_name", "affiliation")
    search_fields = ("user__username", "user__email", "display_name")


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = ("identifier", "ip_address", "attempted_at")
    readonly_fields = ("identifier", "ip_address", "attempted_at")
