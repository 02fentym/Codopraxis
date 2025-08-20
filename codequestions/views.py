# codequestions/views.py
from django.shortcuts import get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_http_methods
import json

from .models import CodeQuestion
from sandbox.utils import run_submission
from .generators import get_or_build_runner


@require_http_methods(["POST"])
def test_submission(request):
    """
    Receives a student's code submission, fetches the correct test runner,
    runs the code in the sandbox, and returns the results.
    """
    try:
        data = json.loads(request.body)
        question_id = data.get("question_id")
        student_code = data.get("student_code")
        language = data.get("language", "python") # Default to python if not specified
    except (json.JSONDecodeError, KeyError):
        return HttpResponseBadRequest("Invalid request body.")

    # Get the CodeQuestion object, or return a 404 if it doesn't exist
    question = get_object_or_404(CodeQuestion, id=question_id)

    # Use the `get_or_build_runner` function to retrieve the correct test runner code
    try:
        runner_code = get_or_build_runner(question, language)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    
    # The `run_submission` function requires the student's code, the test runner,
    # and the full compiled spec for sandbox configuration.
    try:
        result = run_submission(
            solution_code=student_code,
            test_runner_code=runner_code,
            compiled_spec=question.compiled_spec,
        )
        return JsonResponse(result)
    except Exception as e:
        # Catch any unexpected errors during submission execution
        return JsonResponse({"error": f"An unexpected error occurred: {e}"}, status=500)
