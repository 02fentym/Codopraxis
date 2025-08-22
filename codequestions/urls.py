from django.urls import path
from . import views

urlpatterns = [
    # standard I/O
    path("standard-io/builder/", views.standardio_builder, name="standardio-builder"),
    path("standard-io/validate/", views.standardio_validate, name="standardio-validate"),
    path("standard-io/save/", views.standardio_save, name="standardio-save"),
]