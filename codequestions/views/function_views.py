# codequestions/views/function_views.py
from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_http_methods, require_GET, require_POST
from django.views.decorators.csrf import csrf_protect

from ..models import CodeQuestion  # adjust import if your app label differs


# ------------ Helpers ------------

def _json_error(message: str, status: int = 400, errors: Dict[str, Any] | None = None) -> JsonResponse:
    payload = {"ok": False, "message": message}
    if errors:
        payload["errors"] = errors
    return JsonResponse(payload, status=status)


def _parse_json(request: HttpRequest) -> Tuple[Dict[str, Any], JsonResponse | None]:
    try:
        data = json.loads(request.body.decode("utf-8"))
        if not isinstance(data, dict):
            return {}, _json_error("Body must be a JSON object.")
        return data, None
    except json.JSONDecodeError:
        return {}, _json_error("Invalid JSON body.")


# ------------ Validation for Function spec ------------

_ALLOWED_TYPES = {"integer", "float", "string", "bool"}

def _validate_function_spec(spec: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """
    Validates a Function-type question spec.

    Expected shape:
    {
      "version": 1,                          # optional but recommended
      "type": "function",
      "description": "shown to students",
      "function": {
        "name": "factorial",
        "arguments": [
          {"name": "n", "type": "integer"}
        ]
      },
      "tests": [
        {"name": "baseCase", "args": {"n": 0}, "expected": 1},
        {"name": "invalid",  "args": {"n": -1}, "exception": "ValueError"}
      ]
    }
    """
    errors: Dict[str, Any] = {}

    # type
    if spec.get("type") != "function":
        errors["type"] = "type must be 'function'."

    # description (optional but should be string)
    if "description" in spec and not isinstance(spec["description"], str):
        errors["description"] = "description must be a string."

    # function block
    fn = spec.get("function")
    if not isinstance(fn, dict):
        errors["function"] = "function must be an object."
        return False, errors

    fn_name = fn.get("name")
    if not fn_name or not isinstance(fn_name, str):
        errors["function.name"] = "function.name is required (string)."

    arg_list = fn.get("arguments")
    if not isinstance(arg_list, list) or not arg_list:
        errors["function.arguments"] = "function.arguments must be a non-empty list."
        return False, errors

    declared_args: Dict[str, str] = {}
    for i, arg in enumerate(arg_list):
        if not isinstance(arg, dict):
            errors[f"function.arguments[{i}]"] = "Each argument must be an object."
            continue
        an = arg.get("name")
        at = arg.get("type")
        if not an or not isinstance(an, str):
            errors[f"function.arguments[{i}].name"] = "Argument name is required (string)."
        if at not in _ALLOWED_TYPES:
            errors[f"function.arguments[{i}].type"] = f"type must be one of: {', '.join(sorted(_ALLOWED_TYPES))}."
        if an in declared_args:
            errors[f"function.arguments[{i}].name"] = "Duplicate argument name."
        else:
            declared_args[an] = at

    # tests block
    tests = spec.get("tests")
    if not isinstance(tests, list) or len(tests) == 0:
        errors["tests"] = "tests must be a non-empty list."
        return False, errors

    def _type_matches(value: Any, want: str) -> bool:
        if want == "integer":
            return isinstance(value, int) and not isinstance(value, bool)  # bool is subclass of int
        if want == "float":
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if want == "string":
            return isinstance(value, str)
        if want == "bool":
            return isinstance(value, bool)
        return False

    test_names = set()
    for i, t in enumerate(tests):
        if not isinstance(t, dict):
            errors[f"tests[{i}]"] = "Each test must be an object."
            continue

        tname = t.get("name")
        if not tname or not isinstance(tname, str):
            errors[f"tests[{i}].name"] = "Test name is required (string)."
        elif tname in test_names:
            errors[f"tests[{i}].name"] = "Duplicate test name."
        else:
            test_names.add(tname)

        args = t.get("args")
        if not isinstance(args, dict):
            errors[f"tests[{i}].args"] = "args must be an object mapping argument names to values."
            continue

        # Ensure provided args exactly match declared args (same keys)
        provided_keys = set(args.keys())
        declared_keys = set(declared_args.keys())
        if provided_keys != declared_keys:
            missing = declared_keys - provided_keys
            extra = provided_keys - declared_keys
            msg_parts = []
            if missing:
                msg_parts.append(f"missing: {', '.join(sorted(missing))}")
            if extra:
                msg_parts.append(f"unknown: {', '.join(sorted(extra))}")
            errors[f"tests[{i}].args"] = "Argument names must match function signature (" + "; ".join(msg_parts) + ")."
        else:
            # type check each provided value
            for an, want_type in declared_args.items():
                if not _type_matches(args.get(an), want_type):
                    errors[f"tests[{i}].args.{an}"] = f"value should be type {want_type}"

        has_expected = "expected" in t
        has_exception = "exception" in t
        if has_expected and has_exception:
            errors[f"tests[{i}]"] = "Provide either 'expected' or 'exception', not both."
        elif not has_expected and not has_exception:
            errors[f"tests[{i}]"] = "Provide one of 'expected' or 'exception'."
        else:
            if has_exception and not isinstance(t.get("exception"), str):
                errors[f"tests[{i}].exception"] = "exception must be a string (exception class name)."

    ok = len(errors) == 0
    return ok, errors


# ------------ Views ------------

@require_GET
def function_builder(request: HttpRequest) -> HttpResponse:
    """
    Render the Function Builder page.
    (We’ll add the template in the next step: templates/codequestions/function_builder.html)
    """
    ctx = {
        "timeout_default": 5,
        "memory_default": 256,
        "starter_default": "",
    }
    return render(request, "codequestions/function_builder.html", ctx)


@require_POST
@csrf_protect
def function_validate(request: HttpRequest) -> JsonResponse:
    """
    Validate the raw Function spec (JSON body is the spec itself).
    """
    spec, err = _parse_json(request)
    if err:
        return err

    ok, errors = _validate_function_spec(spec)
    if not ok:
        return JsonResponse({"ok": False, "errors": errors}, status=400)

    return JsonResponse({"ok": True})


@require_POST
@csrf_protect
def function_save(request):
    """
    Save a Function-type CodeQuestion.
    Body (JSON):
    {
      "spec": { ... },                 # REQUIRED - function spec JSON
      "timeout_seconds": 5,            # REQUIRED - positive int
      "memory_limit_mb": 256,          # REQUIRED - positive int
      "starter_code": "def f(...):"    # OPTIONAL - stored on model, NOT in spec
    }
    Optional query param: ?id=<pk> to update instead of create.
    """
    # ---- helpers ----
    def json_error(message, status=400, errors=None):
        out = {"ok": False, "message": message}
        if errors: out["errors"] = errors
        return JsonResponse(out, status=status)

    try:
        payload = json.loads(request.body.decode("utf-8"))
        if not isinstance(payload, dict):
            return json_error("Body must be a JSON object.")
    except json.JSONDecodeError:
        return json_error("Invalid JSON body.")

    spec            = payload.get("spec")
    timeout_seconds = payload.get("timeout_seconds")
    memory_limit_mb = payload.get("memory_limit_mb")
    starter_code    = payload.get("starter_code", "")

    # Wrapper validations
    wrapper_errors = {}
    if not isinstance(spec, dict):
        wrapper_errors["spec"] = "spec must be an object."
    if not isinstance(timeout_seconds, int) or timeout_seconds <= 0:
        wrapper_errors["timeout_seconds"] = "Enter a positive integer."
    if not isinstance(memory_limit_mb, int) or memory_limit_mb <= 0:
        wrapper_errors["memory_limit_mb"] = "Enter a positive integer."
    if wrapper_errors:
        return JsonResponse({"ok": False, "errors": wrapper_errors}, status=400)

    # Spec validations (re-use your existing function-spec validator)
    ok, spec_errors = _validate_function_spec(spec)  # assumes helper from Step 1
    if not ok:
        return JsonResponse({"ok": False, "errors": spec_errors}, status=400)

    # Fetch or create
    qid = request.GET.get("id")
    cq = get_object_or_404(CodeQuestion, pk=qid) if qid else CodeQuestion()

    # Set common fields (defensive: support different model field names)
    cq.test_style = "function"
    # description/prompt text for teacher/student display
    if hasattr(cq, "prompt"):
        cq.prompt = spec.get("description", "")
    elif hasattr(cq, "description"):
        cq.description = spec.get("description", "")

    # compiled_spec handling: JSONField or TextField
    def set_compiled_spec(obj, value_dict):
        # prefer compiled_spec if present
        if hasattr(obj, "compiled_spec"):
            # detect field type to decide json.dumps or direct assign
            try:
                field = obj._meta.get_field("compiled_spec")
                if getattr(field, "get_internal_type", lambda: None)() in {"JSONField"}:
                    setattr(obj, "compiled_spec", value_dict)
                else:
                    setattr(obj, "compiled_spec", json.dumps(value_dict))
                return True
            except Exception:
                # fallback to direct assign
                try:
                    setattr(obj, "compiled_spec", value_dict)
                    return True
                except Exception:
                    pass
        # fallbacks if your project used other names
        for alt in ("spec", "spec_json", "raw_spec"):
            if hasattr(obj, alt):
                try:
                    field = obj._meta.get_field(alt)
                    if getattr(field, "get_internal_type", lambda: None)() in {"JSONField"}:
                        setattr(obj, alt, value_dict)
                    else:
                        setattr(obj, alt, json.dumps(value_dict))
                    return True
                except Exception:
                    try:
                        setattr(obj, alt, value_dict)
                        return True
                    except Exception:
                        continue
        return False

    if not set_compiled_spec(cq, spec):
        return json_error("Model has no suitable field to store the compiled spec (looked for compiled_spec/spec/spec_json/raw_spec).")

    # Limits + starter code (if fields exist)
    if hasattr(cq, "timeout_seconds"):
        cq.timeout_seconds = timeout_seconds
    if hasattr(cq, "memory_limit_mb"):
        cq.memory_limit_mb = memory_limit_mb
    if hasattr(cq, "starter_code"):
        cq.starter_code = starter_code

    # If you have a compiler step that generates runner cache, call it here.
    # try:
    #     cq.compile_question()   # optional: keep if your model defines it
    # except ValueError as e:
    #     return JsonResponse({"ok": False, "errors": {"compile": str(e)}}, status=400)

    cq.save()
    return JsonResponse({"ok": True, "id": cq.id})
