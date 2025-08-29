# sandbox/urls.py
from django.urls import path
from . import views  # adjust if using another module path

urlpatterns = [
    path("run/", views.run_code, name="sandbox-run"),
    path("submission/<int:submission_id>/", views.submission_result, name="sandbox-submission"),
    path("submission/<int:submission_id>/view/", views.submission_page, name="sandbox-submission-page"),
    path("submit/", views.submit_code, name="sandbox-submit"),
]
