# codequestions/views/oop_views.py
from __future__ import annotations
import json
from typing import Any, Dict, List, Tuple

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_protect

from ..models import CodeQuestion  # adjust if your app label differs

# ---------- Helpers ----------
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

_ALLOWED_TYPES = {"integer", "float", "string", "bool"}
_ALLOWED_RETURNS = {"void", "integer", "float", "string", "bool"}

def _type_matches(value: Any, want: str) -> bool:
    if want == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if want == "float":
        return (isinstance(value, (int, float)) and not isinstance(value, bool))
    if want == "string":
        return isinstance(value, str)
    if want == "bool":
        return isinstance(value, bool)
    return True  # 'void' or unknown -> validation handles elsewhere

# ---------- OOP spec validation ----------
def _validate_oop_spec(spec: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """
    Expected shape:
    {
      "version": 1,
      "type": "oop",
      "description": "...",
      "class": {
        "name": "Counter",
        "methods": [
          {"name":"__init__", "arguments":[{"name":"n","type":"integer"}], "returns":"void"},
          {"name":"increment","arguments":[], "returns":"void"},
          {"name":"get","arguments":[], "returns":"integer"}
        ]
      },
      "tests": [
        {
          "name":"simple",
          "setup":[{"action":"create","class":"Counter","var":"c","args":[]}],
          "actions":[
            {"action":"call","var":"c","method":"increment","args":[]},
            {"action":"call","var":"c","method":"get","args":[],"expected":1}
          ]
        }
      ]
    }
    """
    errors: Dict[str, Any] = {}

    if spec.get("type") != "oop":
        errors["type"] = "type must be 'oop'."

    # class block
    cls = spec.get("class")
    if not isinstance(cls, dict):
        errors["class"] = "class must be an object."
        return False, errors

    cls_name = cls.get("name")
    if not cls_name or not isinstance(cls_name, str):
        errors["class.name"] = "class.name is required (string)."

    methods = cls.get("methods")
    if not isinstance(methods, list) or len(methods) == 0:
        errors["class.methods"] = "class.methods must be a non-empty list."
        return False, errors

    # Validate methods
    method_map: Dict[str, Dict[str, Any]] = {}
    for i, m in enumerate(methods):
        if not isinstance(m, dict):
            errors[f"class.methods[{i}]"] = "Each method must be an object."
            continue
        mname = m.get("name")
        if not mname or not isinstance(mname, str):
            errors[f"class.methods[{i}].name"] = "Method name is required (string)."
            continue
        if mname in method_map:
            errors[f"class.methods[{i}].name"] = "Duplicate method name."
            continue

        # returns
        ret = m.get("returns", "void")
        if ret not in _ALLOWED_RETURNS:
            errors[f"class.methods[{i}].returns"] = f"returns must be one of: {', '.join(sorted(_ALLOWED_RETURNS))}."

        # args
        arg_list = m.get("arguments", [])
        if not isinstance(arg_list, list):
            errors[f"class.methods[{i}].arguments"] = "arguments must be a list."
            continue
        seen_args = set()
        sig: List[Tuple[str, str]] = []
        for j, a in enumerate(arg_list):
            if not isinstance(a, dict):
                errors[f"class.methods[{i}].arguments[{j}]"] = "Each argument must be an object."
                continue
            an = a.get("name")
            at = a.get("type")
            if not an or not isinstance(an, str):
                errors[f"class.methods[{i}].arguments[{j}].name"] = "Argument name is required (string)."
            if at not in _ALLOWED_TYPES:
                errors[f"class.methods[{i}].arguments[{j}].type"] = f"type must be one of: {', '.join(sorted(_ALLOWED_TYPES))}."
            if an in seen_args:
                errors[f"class.methods[{i}].arguments[{j}].name"] = "Duplicate argument name."
            seen_args.add(an)
            sig.append((an, at))
        method_map[mname] = {"returns": ret, "sig": sig}

    # tests
    tests = spec.get("tests")
    if not isinstance(tests, list) or len(tests) == 0:
        errors["tests"] = "tests must be a non-empty list."
        return False, errors

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

        # setup (optional)
        setup_vars: set[str] = set()
        setup = t.get("setup", [])
        if setup is not None and not isinstance(setup, list):
            errors[f"tests[{i}].setup"] = "setup must be a list."
            setup = []
        for j, s in enumerate(setup):
            if not isinstance(s, dict):
                errors[f"tests[{i}].setup[{j}]"] = "Each setup entry must be an object."
                continue
            if s.get("action") != "create":
                errors[f"tests[{i}].setup[{j}].action"] = "setup action must be 'create'."
                continue
            klass = s.get("class")
            var = s.get("var")
            args = s.get("args", [])
            if not klass or not isinstance(klass, str):
                errors[f"tests[{i}].setup[{j}].class"] = "class is required (string)."
            if not var or not isinstance(var, str):
                errors[f"tests[{i}].setup[{j}].var"] = "var is required (string)."
            elif var in setup_vars:
                errors[f"tests[{i}].setup[{j}].var"] = "Duplicate var name."
            else:
                setup_vars.add(var)
            if not isinstance(args, list):
                errors[f"tests[{i}].setup[{j}].args"] = "args must be an ordered list."

            # Validate ctor signature (if __init__ exists)
            ctor = method_map.get("__init__")
            if ctor:
                if isinstance(args, list) and len(args) != len(ctor["sig"]):
                    errors[f"tests[{i}].setup[{j}].args"] = f"__init__ expects {len(ctor['sig'])} args."
                elif isinstance(args, list):
                    for k, arg_val in enumerate(args):
                        want_type = ctor["sig"][k][1]
                        if not _type_matches(arg_val, want_type):
                            errors[f"tests[{i}].setup[{j}].args[{k}]"] = f"value should be type {want_type}"
            else:
                # no __init__: must pass empty args
                if isinstance(args, list) and len(args) != 0:
                    errors[f"tests[{i}].setup[{j}].args"] = "__init__ not defined; constructor takes no arguments."

        # actions (required)
        actions = t.get("actions")
        if not isinstance(actions, list) or len(actions) == 0:
            errors[f"tests[{i}].actions"] = "actions must be a non-empty list."
            continue

        for j, a in enumerate(actions):
            if not isinstance(a, dict):
                errors[f"tests[{i}].actions[{j}]"] = "Each action must be an object."
                continue
            if a.get("action") != "call":
                errors[f"tests[{i}].actions[{j}].action"] = "action must be 'call'."
                continue
            var = a.get("var")
            method = a.get("method")
            args = a.get("args", [])
            if not var or not isinstance(var, str):
                errors[f"tests[{i}].actions[{j}].var"] = "var is required (string)."
            elif var not in setup_vars:
                errors[f"tests[{i}].actions[{j}].var"] = f"Unknown var '{var}' (define in setup)."
            if not method or not isinstance(method, str):
                errors[f"tests[{i}].actions[{j}].method"] = "method is required (string)."
            elif method not in method_map:
                errors[f"tests[{i}].actions[{j}].method"] = f"Unknown method '{method}'."

            if not isinstance(args, list):
                errors[f"tests[{i}].actions[{j}].args"] = "args must be an ordered list."
            else:
                sig = method_map.get(method, {}).get("sig", [])
                if len(args) != len(sig):
                    errors[f"tests[{i}].actions[{j}].args"] = f"{method} expects {len(sig)} args."
                else:
                    for k, arg_val in enumerate(args):
                        want_type = sig[k][1] if k < len(sig) else None
                        if want_type and not _type_matches(arg_val, want_type):
                            errors[f"tests[{i}].actions[{j}].args[{k}]"] = f"value should be type {want_type}"

            has_expected = "expected" in a
            has_exception = "exception" in a
            if has_expected and has_exception:
                errors[f"tests[{i}].actions[{j}]"] = "Provide either 'expected' or 'exception', not both."
            elif not has_expected and not has_exception:
                # Only require an assertion if method returns non-void
                ret = method_map.get(method, {}).get("returns", "void")
                if ret != "void":
                    errors[f"tests[{i}].actions[{j}]"] = "Non-void method calls must include 'expected' or 'exception'."
            else:
                if has_expected:
                    ret = method_map.get(method, {}).get("returns", "void")
                    if ret == "void":
                        errors[f"tests[{i}].actions[{j}].expected"] = "Void methods cannot have 'expected'."
                    else:
                        if not _type_matches(a.get("expected"), ret):
                            errors[f"tests[{i}].actions[{j}].expected"] = f"expected should be type {ret}"
                if has_exception and not isinstance(a.get("exception"), str):
                    errors[f"tests[{i}].actions[{j}].exception"] = "exception must be a string (exception class name)."

    ok = len(errors) == 0
    return ok, errors

# ---------- Views ----------
@require_GET
def oop_builder(request: HttpRequest) -> HttpResponse:
    ctx = {
        "timeout_default": 5,
        "memory_default": 256,
        "starter_default": "",
    }
    return render(request, "codequestions/oop_builder.html", ctx)

@require_POST
@csrf_protect
def oop_validate(request: HttpRequest) -> JsonResponse:
    spec, err = _parse_json(request)
    if err:
        return err
    ok, errors = _validate_oop_spec(spec)
    if not ok:
        return JsonResponse({"ok": False, "errors": errors}, status=400)
    return JsonResponse({"ok": True})

@require_POST
@csrf_protect
def oop_save(request: HttpRequest) -> JsonResponse:
    """
    Body:
    {
      "spec": { ...oop spec... },
      "timeout_seconds": 5,
      "memory_limit_mb": 256,
      "starter_code": "class Counter: ..."
    }
    Optional: ?id=<pk> to update.
    """
    payload, err = _parse_json(request)
    if err:
        return err

    spec = payload.get("spec")
    timeout_seconds = payload.get("timeout_seconds")
    memory_limit_mb = payload.get("memory_limit_mb")
    starter_code = payload.get("starter_code", "")

    wrapper_errors: Dict[str, Any] = {}
    if not isinstance(spec, dict):
        wrapper_errors["spec"] = "spec must be an object."
    if not isinstance(timeout_seconds, int) or timeout_seconds <= 0:
        wrapper_errors["timeout_seconds"] = "Enter a positive integer."
    if not isinstance(memory_limit_mb, int) or memory_limit_mb <= 0:
        wrapper_errors["memory_limit_mb"] = "Enter a positive integer."
    if wrapper_errors:
        return JsonResponse({"ok": False, "errors": wrapper_errors}, status=400)

    ok, spec_errors = _validate_oop_spec(spec)
    if not ok:
        return JsonResponse({"ok": False, "errors": spec_errors}, status=400)

    qid = request.GET.get("id")
    cq = get_object_or_404(CodeQuestion, pk=qid) if qid else CodeQuestion()

    cq.test_style = "oop"
    # store prompt/description
    if hasattr(cq, "prompt"):
        cq.prompt = spec.get("description", "")
    elif hasattr(cq, "description"):
        cq.description = spec.get("description", "")

    # compiled_spec (JSONField or TextField)
    try:
        field = cq._meta.get_field("compiled_spec")
        if getattr(field, "get_internal_type", lambda: None)() == "JSONField":
            cq.compiled_spec = spec
        else:
            cq.compiled_spec = json.dumps(spec)
    except Exception:
        # fallback common names
        if hasattr(cq, "compiled_spec"):
            cq.compiled_spec = spec
        elif hasattr(cq, "spec"):
            cq.spec = spec
        elif hasattr(cq, "raw_spec"):
            cq.raw_spec = spec
        else:
            return _json_error("Model has no suitable field to store compiled spec.")

    if hasattr(cq, "timeout_seconds"):
        cq.timeout_seconds = timeout_seconds
    if hasattr(cq, "memory_limit_mb"):
        cq.memory_limit_mb = memory_limit_mb
    if hasattr(cq, "starter_code"):
        cq.starter_code = starter_code

    # Optional: compile step if your model defines it
    # try:
    #     cq.compile_question()
    # except ValueError as e:
    #     return _json_error(f"Compilation failed: {e}")

    cq.save()
    return JsonResponse({"ok": True, "id": cq.id})
