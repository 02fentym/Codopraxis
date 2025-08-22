from django.urls import path
from . import views

urlpatterns = [
    path("structural/builder/new/", views.structural_builder, name="structural-builder"),
    path("structural/builder/save/", views.structural_save, name="structural-save"),
]
