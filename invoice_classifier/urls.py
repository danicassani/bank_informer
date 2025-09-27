from django.urls import path

from . import views


urlpatterns = [
    path("", views.index, name="index"),
    path("api/imports/", views.upload_statement, name="upload_statement"),
]

