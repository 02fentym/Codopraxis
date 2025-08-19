from django.urls import path
from . import views

urlpatterns = [
    path("<int:pk>/run/", views.run_script_question, name="codequestion-run"),
]
