import json
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404, render
from .models import CodeQuestion  # adjust import to your app layout


def standardio_builder(request):
    # Try class-level constants first
    timeout_default = getattr(CodeQuestion, "DEFAULT_TIMEOUT_SECONDS", None)
    memory_default  = getattr(CodeQuestion, "DEFAULT_MEMORY_LIMIT_MB", None)

    # Then try model field defaults (if such fields exist)
    if timeout_default is None:
        try:
            timeout_default = CodeQuestion._meta.get_field("timeout_seconds").default
        except Exception:
            timeout_default = None
    if memory_default is None:
        try:
            memory_default = CodeQuestion._meta.get_field("memory_limit_mb").default
        except Exception:
            memory_default = None

    # Final fallback (safe, conventional)
    if timeout_default is None:
        timeout_default = 5
    if memory_default is None:
        memory_default = 128

    return render(
        request,
        "codequestions/standardio_builder.html",
        {
            "timeout_default": timeout_default,
            "memory_default": memory_default,
        },
    )


@require_POST
def standardio_validate(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return HttpResponseBadRequest("Invalid JSON")
    ok, errors = _validate_standardio(payload)
    return JsonResponse({"ok": ok, "errors": errors})


@require_POST
def standardio_save(request):
    """
    Body format (wrapper):
      {
        "spec": { ...standardIo compiled spec... },
        "timeout_seconds": 5,
        "memory_limit_mb": 128
      }
    We save the spec to CodeQuestion.compiled_spec, and write the limits
    onto the model fields (NOT into the JSON).
    """
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return HttpResponseBadRequest("Invalid JSON")

    spec = payload.get("spec")
    if not isinstance(spec, dict):
        return JsonResponse({"ok": False, "errors": {"spec": "Missing or invalid 'spec' object."}}, status=400)

    # Reuse your existing spec validator
    ok, spec_errors = _validate_standardio(spec)

    # Validate limits here (not part of JSON spec)
    errors = dict(spec_errors) if not ok else {}
    timeout_seconds = payload.get("timeout_seconds")
    memory_limit_mb = payload.get("memory_limit_mb")

    def _pos_int(val):
        return isinstance(val, int) and val > 0

    if not _pos_int(timeout_seconds):
        errors["timeout_seconds"] = "timeout_seconds must be a positive integer."
    if not _pos_int(memory_limit_mb):
        errors["memory_limit_mb"] = "memory_limit_mb must be a positive integer."

    if errors:
        return JsonResponse({"ok": False, "errors": errors}, status=400)

    # Create or update
    qid = request.GET.get("id")
    if qid:
        obj = get_object_or_404(CodeQuestion, pk=qid)
    else:
        obj = CodeQuestion()

    # Write fields
    obj.compiled_spec = spec

    # Only set limits if model has these fields
    if hasattr(obj, "timeout_seconds"):
        obj.timeout_seconds = timeout_seconds
    if hasattr(obj, "memory_limit_mb"):
        obj.memory_limit_mb = memory_limit_mb

    obj.save()

    return JsonResponse({"ok": True, "id": obj.pk})

    

# ------- internal validator used by both views --------
def _validate_standardio(payload):
    errors = {}

    if payload.get("type") != "standardIo":
        errors["type"] = "type must be 'standardIo'."

    description = payload.get("description", "")
    if not isinstance(description, str):
        errors["description"] = "description must be a string."

    tests = payload.get("tests", [])
    if not isinstance(tests, list):
        errors["tests"] = "tests must be a list."
        tests = []

    name_counts = {}
    for i, t in enumerate(tests):
        t_errors = {}
        name = (t.get("name") or "").strip()
        stdin = t.get("stdin", "")
        stdout = t.get("stdout", "")

        if not isinstance(name, str):
            t_errors["name"] = "name must be a string."
        if not isinstance(stdin, str):
            t_errors["stdin"] = "stdin must be a string."
        if not isinstance(stdout, str):
            t_errors["stdout"] = "stdout must be a string."

        if not name:
            t_errors["name"] = "name is required."
        name_counts[name] = name_counts.get(name, 0) + 1

        has_content = (isinstance(stdin, str) and stdin.strip() != "") or (isinstance(stdout, str) and stdout.strip() != "")
        if has_content and isinstance(stdout, str) and stdout.strip() == "":
            t_errors["stdout"] = "stdout is required when a test has input/output."

        if isinstance(stdout, str) and stdout and not stdout.endswith("\n"):
            t_errors["stdout"] = (t_errors.get("stdout", "") + (" " if t_errors.get("stdout") else "") + "hint: runner expects trailing \\n.")

        if t_errors:
            errors[f"tests[{i}]"] = t_errors

    for i, t in enumerate(tests):
        name = (t.get("name") or "").strip()
        if name and name_counts.get(name, 0) > 1:
            errors.setdefault(f"tests[{i}]", {})
            errors[f"tests[{i}]"]["name"] = "name must be unique."

    return (len(errors) == 0), errors
