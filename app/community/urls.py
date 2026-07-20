from django.urls import path

from . import views

app_name = "community"

urlpatterns = [
    path("", views.team_library, name="library"),
]
