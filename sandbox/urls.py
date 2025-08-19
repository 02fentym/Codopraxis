from django.urls import path
from . import views

urlpatterns = [
    path("run/<int:pk>/", views.run_script_question, name="sandbox-run-script"),
]
