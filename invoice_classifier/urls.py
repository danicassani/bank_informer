from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("visualizador/", views.visualizer, name="visualizer_legacy"),
    path("upload-csv/", views.upload_csv, name="upload_csv"),
    path("api/imports/", views.upload_statement, name="upload_statement"),
    path(
        "criterios/",
        views.manage_classification_criteria,
        name="manage_classification_criteria",
    ),
    path("login/", views.login_view, name="login"),
    path("sign-up/", views.sign_up, name="sign_up"),
    path("logout/", views.logout_view, name="logout"),
]

