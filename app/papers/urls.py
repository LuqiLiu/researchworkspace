from django.urls import path

from . import views

app_name = "papers"

urlpatterns = [
    path("import/", views.paper_import, name="import"),
    path("<int:pk>/bibtex/", views.bibtex_export, name="bibtex"),
]
