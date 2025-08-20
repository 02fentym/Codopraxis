from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from .forms import CodeSubmissionForm
from .utils import run_submission
from codequestions.models import CodeQuestion

@login_required
@require_http_methods(["GET", "POST"])
def run_question_view(request, test_style: str, pk: int):
    question = get_object_or_404(CodeQuestion, pk=pk)
    specs = question.compiled_spec or {}

    # Make sure the compiled spec matches the URL's test_style
    if specs.get("test_style") != test_style:
        return render(request, "codequestions/run_not_supported.html", {
            "question": question,
            "reason": f"Mismatched test style. URL expects '{test_style}' but question is '{specs.get('test_style')}'",
        })

    results = None
    form = CodeSubmissionForm(
        request.POST or None,
        initial={"code": question.starter_code}
    )

    if request.method == "POST" and form.is_valid():
        code = form.cleaned_data["code"]
        results = run_submission(specs, code, language="python")

    return render(request, "sandbox/run_script.html", {
        "question": question,
        "form": form,
        "results": results,
    })

# Keep this view for backward compatibility
@login_required
@require_http_methods(["GET", "POST"])
def run_script_question(request, pk: int):
    question = get_object_or_404(CodeQuestion, pk=pk)
    specs = question.compiled_spec or {}
    if specs.get("test_style") != "script":
        return render(request, "codequestions/run_not_supported.html", {
            "question": question,
            "reason": "This page only supports test_style='script'.",
        })

    results = None
    form = CodeSubmissionForm(
        request.POST or None,
        initial={"code": question.starter_code}
    )

    if request.method == "POST" and form.is_valid():
        code = form.cleaned_data["code"]
        results = run_submission(specs, code, language="python")

    return render(request, "sandbox/run_script.html", {
        "question": question,
        "form": form,
        "results": results,
    })