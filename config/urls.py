from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("app.accounts.urls")),
    path("comments/", include("app.comments.urls")),
    path("papers/", include("app.papers.urls")),
    path("projects/", include("app.projects.urls")),
    path("shared/", include("app.sharing.urls")),
    path("workspace/", include("app.research_objects.urls")),
    path("", include("app.core.urls")),
]
