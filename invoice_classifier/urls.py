from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("visualizador/", views.visualizer, name="visualizer"),
    path("api/imports/", views.upload_statement, name="upload_statement"),
    path("debug/sql/", views.debug_sql_console, name="debug_sql_console"),
    path(
        "criterios/",
        views.manage_classification_criteria,
        name="manage_classification_criteria",
    ),
]

