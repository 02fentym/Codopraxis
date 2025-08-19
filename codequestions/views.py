from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django import forms

from .models import CodeQuestion
from sandbox.utils import run_submission


class CodeSubmissionForm(forms.Form):
    code = forms.CharField(
        widget=forms.Textarea(attrs={
            "rows": 14,
            "class": "textarea textarea-bordered w-full font-mono text-sm",
            "placeholder": "# write your solution here\nprint('Hello, world!')",
        }),
        label="Your solution (solution.py)",
        required=True,
    )


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
        # ⬇️ your two lines, now in context
        results = run_submission(specs, code, language="python")

    return render(request, "codequestions/run_script.html", {
        "question": question,
        "form": form,
        "results": results,
    })
