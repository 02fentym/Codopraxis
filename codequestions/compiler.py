# codequestions/compiler.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, TypedDict, Literal
from django.utils import timezone

# -------------------------------------------------------------------
# Types
# -------------------------------------------------------------------

Style = Literal["script", "function", "oop"]


class ScriptCase(TypedDict, total=False):
    input: str
    output: str


class FunctionCase(TypedDict, total=False):
    args: List[Any]
    output: str
    expected: Any


class OopCase(TypedDict, total=False):
    setup: List[str]
    calls: List[str]
    expected: Dict[str, Any]
    output: str


@dataclass
class CompileResult:
    spec: Dict[str, Any]
    count: int


# -------------------------------------------------------------------
# Sandbox defaults (applied to every compiled spec unless overridden)
# -------------------------------------------------------------------
SANDBOX_DEFAULTS: Dict[str, Any] = {
    "timeout_seconds": 2,
    # If None/omitted, we'll set overall_timeout_seconds = 2 * timeout_seconds
    "overall_timeout_seconds": None,
    "memory_limit_mb": 128,
    "cpus": 1,
    "docker_image": "python:3.12-slim",
    "stop_on_timeout": True,
}


# -------------------------------------------------------------------
# Case normalizers (ensure predictable shape per style)
# -------------------------------------------------------------------
def normalize_script(case: Dict[str, Any]) -> ScriptCase:
    if "output" not in case or case["output"] is None:
        raise ValueError("script case requires 'output'")
    return {
        "input": case.get("input", "") or "",
        "output": case["output"],
    }


def normalize_function(case: Dict[str, Any]) -> FunctionCase:
    return {
        "args": case.get("args", []) or [],
        "output": case.get("output", "") or "",
        "expected": case.get("expected", None),
    }


def normalize_oop(case: Dict[str, Any]) -> OopCase:
    return {
        "setup": case.get("setup", []) or [],
        "calls": case.get("calls", []) or [],
        "expected": case.get("expected", {}) or {},
        "output": case.get("output", "") or "",
    }


def normalize_case(style: Style, payload: Dict[str, Any]) -> Dict[str, Any]:
    if style == "script":
        return normalize_script(payload)
    if style == "function":
        return normalize_function(payload)
    if style == "oop":
        return normalize_oop(payload)
    raise ValueError(f"Unknown test_style: {style}")


# -------------------------------------------------------------------
# Compiler
# -------------------------------------------------------------------
def compile_question(question) -> CompileResult:
    """
    Build the compiled spec snapshot used by the runner.
    - Shapes cases consistently by style.
    - Applies sandbox defaults (Docker image, CPU/RAM caps, timeouts).
    - Allows safe overrides from the question model if present.
    Persists the compiled_spec + bumps compiled_version.
    """
    style: Style = question.test_style  # "script" | "function" | "oop"
    cases_qs = question.test_cases.filter(is_active=True).order_by("order", "id")

    # Normalize each row's payload to enforce defaults
    normalized_cases: List[Dict[str, Any]] = []
    for tc in cases_qs:
        normalized_cases.append(normalize_case(style, dict(tc.data or {})))

    # Base spec by style
    if style == "script":
        spec: Dict[str, Any] = {"test_style": "script", "test_cases": normalized_cases}
    elif style == "function":
        spec = {"test_style": "function", "test_cases": normalized_cases}
        # If/when you add a function name to the model:
        # spec["function"] = (question.function_name or "").strip()
    elif style == "oop":
        spec = {"test_style": "oop", "test_cases": normalized_cases}
    else:
        raise ValueError(f"Unknown test_style: {style}")

    # ---- Apply sandbox defaults first
    spec = {**SANDBOX_DEFAULTS, **spec}

    # ---- Pull per-question timeout if the model provides it
    # (keeps backward compatibility with your previous field)
    model_timeout = getattr(question, "timeout_seconds", None)
    if model_timeout is not None:
        spec["timeout_seconds"] = float(model_timeout)

    # If overall not specified, set to 2 * timeout_seconds
    if not spec.get("overall_timeout_seconds"):
        spec["overall_timeout_seconds"] = float(spec["timeout_seconds"]) * 2

    # ---- Optional: let explicit question fields override defaults if they exist
    # Only override if the attribute exists on the model and is not None/empty.
    for field in ("memory_limit_mb", "cpus", "docker_image", "stop_on_timeout", "overall_timeout_seconds"):
        if hasattr(question, field):
            val = getattr(question, field)
            if val not in (None, ""):
                spec[field] = val

    # Persist snapshot on the question
    question.compiled_spec = spec
    question.compiled_at = timezone.now()
    question.compiled_version = (question.compiled_version or 0) + 1
    question.save(update_fields=["compiled_spec", "compiled_at", "compiled_version"])

    return CompileResult(spec=spec, count=len(normalized_cases))
