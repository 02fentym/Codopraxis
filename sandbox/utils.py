# sandbox/utils.py
from __future__ import annotations
import subprocess, sys, tempfile, os, textwrap
from typing import Dict, Any, List

def run_script_tests(compiled_specs: Dict[str, Any], submission_code: str) -> Dict[str, Any]:
    """
    Execute a student's script (solution.py) against script-style test cases.
    Returns a dict with overall status and per-case results.
    """
    assert compiled_specs.get("test_style") == "script", "This runner only supports test_style='script'."

    cases: List[Dict[str, Any]] = compiled_specs.get("test_cases", [])
    timeout = compiled_specs.get("timeout_seconds", 5)

    submission_code = textwrap.dedent(submission_code).lstrip()

    results = []
    passed_count = 0

    with tempfile.TemporaryDirectory() as td:
        solution_path = os.path.join(td, "solution.py")
        with open(solution_path, "w", encoding="utf-8") as f:
            f.write(submission_code)

        for idx, case in enumerate(cases, start=1):
            input_data = case.get("input", "")
            expected = case.get("output", "")
            try:
                proc = subprocess.run(
                    [sys.executable, "-u", solution_path],
                    input=input_data.encode("utf-8"),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=timeout,
                    check=False,
                )
                stdout = proc.stdout.decode("utf-8", errors="replace")
                stderr = proc.stderr.decode("utf-8", errors="replace")
                ok = (stdout == expected)
                results.append({
                    "case": idx,
                    "input": input_data,
                    "expected": expected,
                    "stdout": stdout,
                    "stderr": stderr,
                    "passed": ok,
                    "returncode": proc.returncode,
                    "timeout": False,
                })
                if ok:
                    passed_count += 1
            except subprocess.TimeoutExpired as e:
                results.append({
                    "case": idx,
                    "input": input_data,
                    "expected": expected,
                    "stdout": e.stdout.decode("utf-8", errors="replace") if e.stdout else "",
                    "stderr": e.stderr.decode("utf-8", errors="replace") if e.stderr else "",
                    "passed": False,
                    "returncode": None,
                    "timeout": True,
                })

    return {
        "test_style": "script",
        "total": len(cases),
        "passed": passed_count,
        "failed": len(cases) - passed_count,
        "results": results,
    }



SUPPORTED_LANGS = {"python"}  # expand later

def run_submission(compiled_specs: Dict[str, Any], submission_code: str, *, language: str = "python") -> Dict[str, Any]:
    """
    Single entry-point for grading code submissions.
    Returns a normalized result dict:
      {
        "ok": bool,
        "test_style": "script" | "function" | "oop",
        "total": int, "passed": int, "failed": int,
        "results": [ {case, input, expected, stdout, stderr, passed, timeout, returncode}, ... ],
        "meta": {"language": "..."}
      }
    """
    if language not in SUPPORTED_LANGS:
        return {
            "ok": False,
            "error": f"Unsupported language: {language}",
            "meta": {"language": language}
        }

    style = compiled_specs.get("test_style")
    if style == "script":
        res = run_script_tests(compiled_specs, submission_code)
    elif style == "function":
        # placeholder for future expansion
        return {"ok": False, "error": "Function style not implemented yet.", "meta": {"language": language}}
    elif style == "oop":
        return {"ok": False, "error": "OOP style not implemented yet.", "meta": {"language": language}}
    else:
        return {"ok": False, "error": f"Unknown test_style: {style}", "meta": {"language": language}}

    res["ok"] = (res.get("failed", 0) == 0)
    res["meta"] = {"language": language}
    return res
