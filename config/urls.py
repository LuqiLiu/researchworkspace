from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("app.accounts.urls")),
    path("workspace/", include("app.research_objects.urls")),
    path("", include("app.core.urls")),
]
