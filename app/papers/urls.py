from django.urls import path

from . import views

app_name = "papers"

urlpatterns = [
    path("import/", views.paper_import, name="import"),
    path("export.csv", views.csv_export, name="csv_export"),
    path("<int:pk>/metadata/", views.metadata_edit, name="metadata_edit"),
    path("<int:pk>/bibtex/", views.bibtex_export, name="bibtex"),
]
