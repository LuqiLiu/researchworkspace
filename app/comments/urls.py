from django.urls import path

from . import views

app_name = "comments"

urlpatterns = [
    path("objects/<int:object_pk>/create/", views.comment_create, name="create"),
    path("<int:pk>/delete/", views.comment_delete, name="delete"),
]
