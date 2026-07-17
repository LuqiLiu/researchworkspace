from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .forms import EmailOrUsernameAuthenticationForm, UserProfileForm
from .models import LoginAttempt


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (forwarded.split(",")[0].strip() or request.META.get("REMOTE_ADDR")) or None


class ThrottledLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = EmailOrUsernameAuthenticationForm
    redirect_authenticated_user = True
    window = timedelta(minutes=15)
    max_attempts = 5

    def post(self, request, *args, **kwargs):
        identifier = request.POST.get("username", "").strip().lower()
        ip_address = _client_ip(request)
        recent = LoginAttempt.objects.filter(
            attempted_at__gte=timezone.now() - self.window,
        ).filter(Q(identifier=identifier) | Q(ip_address=ip_address))
        if identifier and recent.count() >= self.max_attempts:
            return render(
                request,
                self.template_name,
                {"form": self.get_form(), "rate_limited": True},
                status=429,
            )

        form = self.get_form()
        if form.is_valid():
            LoginAttempt.objects.filter(
                identifier=identifier,
                ip_address=ip_address,
            ).delete()
            login(request, form.get_user())
            return redirect(self.get_success_url())

        if identifier:
            LoginAttempt.objects.create(
                identifier=identifier,
                ip_address=ip_address,
            )
        return self.form_invalid(form)


@login_required
@require_http_methods(["GET", "POST"])
def profile(request):
    from .models import UserProfile

    profile_instance, _ = UserProfile.objects.get_or_create(user=request.user)
    form = UserProfileForm(
        request.POST or None,
        request.FILES or None,
        instance=profile_instance,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "个人资料已保存。")
        return redirect("accounts:profile")
    return render(request, "accounts/profile.html", {"form": form})
