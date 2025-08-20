from django.urls import path
from . import views

urlpatterns = [
    path("standard-io/builder/", views.standardio_builder, name="standardio-builder"),
    path("standard-io/validate/", views.standardio_validate, name="standardio-validate"),
]
