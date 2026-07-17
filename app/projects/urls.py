from django.urls import path

from . import views

app_name = "projects"

urlpatterns = [
    path("", views.project_list, name="list"),
    path("new/", views.project_create, name="create"),
    path("<int:pk>/", views.project_detail, name="detail"),
    path("<int:pk>/edit/", views.project_edit, name="edit"),
    path("<int:project_pk>/members/add/", views.member_add, name="member_add"),
    path("members/<int:pk>/update/", views.member_update, name="member_update"),
    path("members/<int:pk>/remove/", views.member_remove, name="member_remove"),
]
