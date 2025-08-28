# sandbox/urls.py
from django.urls import path
from .views import run_code  # adjust if using another module path

urlpatterns = [
    path("run/", run_code, name="sandbox-run"),
]
