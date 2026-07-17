from django.urls import path

from . import views

app_name = "research_objects"

urlpatterns = [
    path("", views.object_list, name="list"),
    path("new/", views.object_create, name="create"),
    path("search/", views.search, name="search"),
    path("<int:pk>/", views.object_detail, name="detail"),
    path("<int:pk>/edit/", views.object_edit, name="edit"),
    path("<int:pk>/autosave/", views.object_autosave, name="autosave"),
    path("<int:pk>/relations/", views.relation_create, name="relation_create"),
    path("relations/<int:pk>/delete/", views.relation_delete, name="relation_delete"),
    path("<int:pk>/toggle/<str:field>/", views.object_toggle, name="toggle"),
    path("<int:pk>/delete/", views.object_delete, name="delete"),
    path("<int:pk>/export/", views.object_export, name="export"),
    path("<int:pk>/attachments/", views.attachment_upload, name="attachment_upload"),
    path(
        "attachments/<int:pk>/download/",
        views.attachment_download,
        name="attachment_download",
    ),
]
