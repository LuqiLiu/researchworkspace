from django.urls import path

from . import views

app_name = "sharing"

urlpatterns = [
    path("", views.shared_with_me, name="shared_with_me"),
    path("objects/<int:object_pk>/create/", views.share_create, name="create"),
    path("<int:pk>/update/", views.share_update, name="update"),
    path("<int:pk>/revoke/", views.share_revoke, name="revoke"),
]
