from django.urls import path
from . import views

urlpatterns = [
    # This URL is deprecated, but we keep it for backward compatibility
    path("run/<int:pk>/", views.run_script_question, name="sandbox-run-script"),
    # New, generic URL for all question types
    path("run/<str:test_style>/<int:pk>/", views.run_question_view, name="sandbox-run"),
]