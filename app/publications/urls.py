from django.urls import path

from . import views

app_name = "publications"

urlpatterns = [
    path("robots.txt", views.robots_txt, name="robots"),
    path("publications/", views.manage_list, name="manage_list"),
    path("publications/export/", views.public_profile_export, name="profile_export"),
    path("publications/from/<int:source_pk>/", views.edit_from_source, name="edit_from_source"),
    path("publications/<int:pk>/preview/", views.preview, name="preview"),
    path("publications/<int:pk>/preview-cover/", views.preview_cover, name="preview_cover"),
    path("publications/files/<int:pk>/preview/", views.preview_attachment, name="preview_attachment"),
    path("publications/<int:pk>/publish/", views.publish, name="publish"),
    path("publications/<int:pk>/withdraw/", views.withdraw, name="withdraw"),
    path("u/<str:public_slug>/avatar/", views.profile_avatar, name="profile_avatar"),
    path("u/<str:public_slug>/publications/", views.public_publications, name="public_publications"),
    path("u/<str:public_slug>/notes/<str:snapshot_slug>/", views.public_detail, name="public_detail"),
    path("u/<str:public_slug>/", views.public_profile, name="public_profile"),
    path("public-files/<int:pk>/download/", views.public_attachment, name="public_attachment"),
    path("public-covers/<int:pk>/", views.snapshot_cover, name="snapshot_cover"),
]
