from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from codequestions.models import CodeQuestion
from sandbox.models import Language, Runtime

@login_required(login_url="login")
def home(request):
    return render(request, "base/home.html")


def gate_to_home_or_login(request):
    if request.user.is_authenticated:
        return render(request, "base/home.html")  # your base app’s home
    # preserve ?next so they come back to "/"
    login_url = reverse("login")
    return redirect(f"{login_url}?next=/")


@login_required
def try_codequestion_page(request, question_id: int):
    """
    Student-facing page that lets you try a CodeQuestion in an Ace editor
    and POST to the sandbox-run API.
    """
    question = get_object_or_404(CodeQuestion, id=question_id)

    # Allow ?lang=python, default to python
    language_slug = (request.GET.get("lang") or "python").lower()
    language = get_object_or_404(Language, slug=language_slug, is_active=True)

    # Prefer the default runtime for that language
    runtime = (Runtime.objects.filter(language=language, is_default=True).first()
               or get_object_or_404(Runtime, language=language))

    context = {
        "question": question,
        "language": language,
        "runtime": runtime,
        "api_url": reverse("sandbox-run", args=[question.id]),  # calls the sandbox API
        "ace_mode": language.syntax_highlighter_mode or language.slug,  # e.g., "python"
        "entry_filename": runtime.default_entry_filename,               # e.g., "solution.py"
    }
    return render(request, "base/try_codequestion.html", context)
