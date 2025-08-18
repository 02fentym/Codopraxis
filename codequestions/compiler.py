from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, TypedDict, Literal
from django.utils import timezone

# Types
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

# Defaults per style
def normalize_script(case: Dict[str, Any]) -> ScriptCase:
    if "output" not in case or case["output"] is None:
        raise ValueError("script case requires 'output'")
    return {"input": case.get("input", ""), "output": case["output"]}

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

def compile_question(question) -> CompileResult:
    """
    Build the single compiled spec used by test generators.
    Uses active, ordered test cases on the question.
    """
    style: Style = question.test_style  # "script" | "function" | "oop"
    cases_qs = question.test_cases.filter(is_active=True).order_by("order", "id")

    # Normalize each row's payload to enforce defaults
    normalized_cases: List[Dict[str, Any]] = []
    for tc in cases_qs:
        normalized_cases.append(normalize_case(style, dict(tc.data or {})))

    # Shape compiled spec by style
    if style == "script":
        spec = {"test_style": "script", "test_cases": normalized_cases}
    elif style == "function":
        # Note: function name lives on each *question*, not case (you can add later)
        spec = {"test_style": "function", "test_cases": normalized_cases}
    elif style == "oop":
        spec = {"test_style": "oop", "test_cases": normalized_cases}
    else:
        raise ValueError(f"Unknown test_style: {style}")

    # Persist snapshot on the question
    question.compiled_spec = spec
    question.compiled_at = timezone.now()
    question.compiled_version = (question.compiled_version or 0) + 1
    question.save(update_fields=["compiled_spec", "compiled_at", "compiled_version"])

    return CompileResult(spec=spec, count=len(normalized_cases))
