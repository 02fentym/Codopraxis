from django.shortcuts import render
import json
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt  # not needed if you pass CSRF from the form

def standardio_builder(request):
    return render(request, "codequestions/standardio_builder.html")


def standardio_builder(request):
    return render(request, "codequestions/standardio_builder.html")


@require_POST
def standardio_validate(request):
    # If you POST from the same page with CSRF, use request.body;
    # if you prefer form field, do: spec_json = request.POST.get("spec")
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return HttpResponseBadRequest("Invalid JSON")

    errors = {}

    # Basic shape
    if payload.get("type") != "standardIo":
        errors["type"] = "type must be 'standardIo'."

    description = payload.get("description", "")
    if not isinstance(description, str):
        errors["description"] = "description must be a string."

    tests = payload.get("tests", [])
    if not isinstance(tests, list):
        errors["tests"] = "tests must be a list."
        tests = []

    # Per-test checks
    name_counts = {}
    for i, t in enumerate(tests):
        t_errors = {}
        name = t.get("name", "").strip()
        stdin = t.get("stdin", "")
        stdout = t.get("stdout", "")

        # types
        if not isinstance(name, str):
            t_errors["name"] = "name must be a string."
        if not isinstance(stdin, str):
            t_errors["stdin"] = "stdin must be a string."
        if not isinstance(stdout, str):
            t_errors["stdout"] = "stdout must be a string."

        # name required & unique
        if not name:
            t_errors["name"] = "name is required."
        name_counts[name] = name_counts.get(name, 0) + 1

        # stdout required if test has any content
        has_content = (stdin.strip() != "") or (stdout.strip() != "")
        if has_content and stdout.strip() == "":
            t_errors["stdout"] = "stdout is required when a test has input/output."

        # normalize: ensure trailing newline (server doesn’t mutate—just warn)
        if isinstance(stdout, str) and stdout and not stdout.endswith("\n"):
            t_errors.setdefault("stdout", "");  # make sure key exists
            # append hint (don’t overwrite existing message)
            t_errors["stdout"] = (t_errors["stdout"] + " " if t_errors["stdout"] else "") + "hint: runner expects trailing \\n."

        if t_errors:
            errors[f"tests[{i}]"] = t_errors

    # uniqueness pass
    for i, t in enumerate(tests):
        name = (t.get("name") or "").strip()
        if name and name_counts.get(name, 0) > 1:
            errors.setdefault(f"tests[{i}]", {})
            errors[f"tests[{i}]"]["name"] = "name must be unique."

    ok = (len(errors) == 0)
    return JsonResponse({"ok": ok, "errors": errors})
