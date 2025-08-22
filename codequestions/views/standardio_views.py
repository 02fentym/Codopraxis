# codequestions/views/standardio_views.py
import json
from typing import Dict, Any, List
from django.db import transaction
from django.http import JsonResponse, HttpRequest
from django.shortcuts import render
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.core.exceptions import ValidationError
from codequestions.models import CodeQuestion, StandardIOQuestion, FunctionOOPQuestion

def standardio_builder(request):
    """
    Render the Standard I/O builder page.
    """
    context = {
        "timeout_default": 5,
        "memory_default": 128,
    }
    return render(request, "codequestions/standardio_builder.html", context)


# ---------- Helpers ----------

def _json_error(message: str, status: int = 400, errors: Dict[str, Any] | None = None):
    payload = {"ok": False, "message": message}
    if errors:
        payload["errors"] = errors
    return JsonResponse(payload, status=status)

def _parse_json(request: HttpRequest) -> Dict[str, Any] | None:
    try:
        return json.loads(request.body.decode("utf-8"))
    except Exception:
        return None

def _validate_tests_json(tests_json: Dict[str, Any]) -> Dict[str, str]:
    """
    Returns field-error dict. Empty dict means OK.
    Expect shape: {"tests": [ { "name": str, "stdin": str, "stdout": str }, ... ]}
    """
    errors: Dict[str, str] = {}
    if not isinstance(tests_json, dict):
        return {"tests_json": "Expected an object."}
    tests = tests_json.get("tests")
    if not isinstance(tests, list) or len(tests) == 0:
        return {"tests": "Provide at least one test."}

    names: List[str] = []
    for i, t in enumerate(tests):
        if not isinstance(t, dict):
            errors[f"tests[{i}]"] = "Each test must be an object."
            continue
        name = t.get("name", "")
        stdout = t.get("stdout", "")
        # stdin optional; coerce to string if present
        if "stdin" in t and not isinstance(t.get("stdin"), str):
            errors[f"tests[{i}].stdin"] = "stdin must be a string."
        if not isinstance(name, str) or not name.strip():
            errors[f"tests[{i}].name"] = "Name is required."
        else:
            names.append(name.strip())
        if not isinstance(stdout, str) or not stdout.strip():
            errors[f"tests[{i}].stdout"] = "stdout is required."
        elif not stdout.endswith("\n"):
            errors[f"tests[{i}].stdout"] = "stdout must end with a newline (\\n)."

    # uniqueness of names
    seen = set()
    for i, n in enumerate(names):
        if n in seen:
            errors[f"tests[{i}].name"] = "Duplicate test name."
        seen.add(n)

    return errors


# ---------- Endpoints ----------

@require_POST
@csrf_protect
def standardio_validate(request: HttpRequest):
    """
    Input: raw tests_json (the inner object), e.g.
      { "tests": [ { "name": "t1", "stdin": "", "stdout": "ok\\n" } ] }
    Output: { ok: true } or { ok: false, errors: {...} }
    """
    data = _parse_json(request)
    if data is None:
        return _json_error("Invalid JSON body.")
    errors = _validate_tests_json(data)
    if errors:
        return JsonResponse({"ok": False, "errors": errors}, status=400)
    return JsonResponse({"ok": True})


@require_POST
@csrf_protect
def standardio_save(request: HttpRequest):
    """
    Input: full authoring payload:
    {
      "id": 123?,  // optional for update
      "question_type": "standard_io",
      "prompt": "...",
      "timeout_seconds": 5,
      "memory_limit_mb": 128,
      "standard_io": {
        "tests_json": { "tests": [...] }
      }
    }
    Output: { ok: true, id: <CodeQuestion.id> } or { ok: false, errors: {...} }
    """
    payload = _parse_json(request)
    if payload is None:
        return _json_error("Invalid JSON body.")

    # Top-level requireds
    errors: Dict[str, Any] = {}
    if payload.get("question_type") != CodeQuestion.QuestionType.STANDARD_IO:
        errors["question_type"] = "Must be 'standard_io'."

    prompt = (payload.get("prompt") or "").strip()
    if not prompt:
        errors["prompt"] = "Prompt is required."

    timeout_seconds = payload.get("timeout_seconds")
    if not isinstance(timeout_seconds, int) or timeout_seconds <= 0:
        errors["timeout_seconds"] = "Timeout must be a positive integer."

    memory_limit_mb = payload.get("memory_limit_mb")
    if not isinstance(memory_limit_mb, int) or memory_limit_mb <= 0:
        errors["memory_limit_mb"] = "Memory limit must be a positive integer."

    stdio_block = payload.get("standard_io") or {}
    tests_json = stdio_block.get("tests_json")

    test_errs = _validate_tests_json(tests_json) if tests_json is not None else {"tests_json": "tests_json is required."}
    errors.update(test_errs)

    if errors:
        return JsonResponse({"ok": False, "errors": errors}, status=400)

    # Create or update
    q_id = payload.get("id")
    try:
        with transaction.atomic():
            if q_id:
                # Update
                cq = CodeQuestion.objects.select_for_update().get(id=q_id)
                if cq.question_type != CodeQuestion.QuestionType.STANDARD_IO:
                    return _json_error("Cannot update: existing question is not 'standard_io'.", status=409)
                # guard: cannot have function/oop rows
                if FunctionOOPQuestion.objects.filter(code_question=cq).exists():
                    return _json_error("This question already has Function/OOP specs; cannot convert to Standard I/O.", status=409)

                cq.prompt = prompt
                cq.timeout_seconds = timeout_seconds
                cq.memory_limit_mb = memory_limit_mb
                cq.full_clean()
                cq.save()

                stdio, _ = StandardIOQuestion.objects.get_or_create(code_question=cq)
                stdio.tests_json = tests_json
                stdio.full_clean()
                stdio.save()
            else:
                # Create
                cq = CodeQuestion.objects.create(
                    question_type=CodeQuestion.QuestionType.STANDARD_IO,
                    prompt=prompt,
                    timeout_seconds=timeout_seconds,
                    memory_limit_mb=memory_limit_mb,
                )
                StandardIOQuestion.objects.create(
                    code_question=cq,
                    tests_json=tests_json,
                )

    except ValidationError as ve:
        # Model-level clean() errors
        model_errors = {}
        for field, msgs in ve.message_dict.items():
            model_errors[field] = "; ".join(msgs) if isinstance(msgs, list) else str(msgs)
        return JsonResponse({"ok": False, "errors": model_errors}, status=400)
    except CodeQuestion.DoesNotExist:
        return _json_error("Question not found for update.", status=404)

    return JsonResponse({"ok": True, "id": cq.id})
