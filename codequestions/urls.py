from django.urls import path
from . import views

urlpatterns = [
    # standard I/O
    path("standard-io/builder/", views.standardio_builder, name="standardio-builder"),
    path("standard-io/validate/", views.standardio_validate, name="standardio-validate"),
    path("standard-io/save/", views.standardio_save, name="standardio-save"),

    # function
    path("function/builder/", views.function_builder, name="function-builder"),
    path("function/validate/", views.function_validate, name="function-validate"),
    path("function/save/", views.function_save, name="function-save"),
]
