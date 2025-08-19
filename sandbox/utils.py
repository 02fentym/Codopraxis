# sandbox/utils.py
from __future__ import annotations
import subprocess, sys, tempfile, os, textwrap, signal, time
from typing import Dict, Any, List


def run_script_tests(compiled_specs: Dict[str, Any], submission_code: str) -> Dict[str, Any]:
    assert compiled_specs.get("test_style") == "script", "This runner only supports test_style='script'."

    cases: List[Dict[str, Any]] = compiled_specs.get("test_cases", [])
    case_timeout = float(compiled_specs.get("timeout_seconds", 5))
    # New knobs (safe defaults)
    overall_cap = float(compiled_specs.get("overall_timeout_seconds", case_timeout * 2))
    stop_on_timeout = bool(compiled_specs.get("stop_on_timeout", True))

    submission_start = time.monotonic()
    # helper: how much budget remains for the whole submission
    def submission_time_left() -> float:
        return max(0.0, overall_cap - (time.monotonic() - submission_start))

    submission_timed_out = False
    results = []
    passed_count = 0

    # write solution once per submission (still exec per case)
    with tempfile.TemporaryDirectory() as td:
        solution_path = os.path.join(td, "solution.py")
        with open(solution_path, "w", encoding="utf-8") as f:
            f.write(textwrap.dedent(submission_code).lstrip())

        for idx, case in enumerate(cases, start=1):
            # If we blew the overall cap already, bail
            if submission_time_left() <= 0:
                submission_timed_out = True
                results.append({
                    "case": idx,
                    "input": case.get("input", ""),
                    "expected": case.get("output", ""),
                    "stdout": "",
                    "stderr": "Submission overall time budget exceeded.",
                    "passed": False,
                    "returncode": None,
                    "timeout": True,
                })
                break

            input_data = case.get("input", "")
            expected = case.get("output", "")

            # Per-case timeout cannot exceed remaining submission budget
            this_timeout = min(case_timeout, submission_time_left())

            try:
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
                proc = subprocess.Popen(
                    [sys.executable, "-u", "-B", solution_path],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True,
                    start_new_session=(os.name != "nt"),
                    creationflags=creationflags,
                )
                stdout, stderr = proc.communicate(input=input_data, timeout=this_timeout)
                ok = (stdout == expected)

                results.append({
                    "case": idx, "input": input_data, "expected": expected,
                    "stdout": stdout, "stderr": stderr,
                    "passed": ok, "returncode": proc.returncode, "timeout": False,
                })
                if ok:
                    passed_count += 1

            except subprocess.TimeoutExpired:
                # Kill hard and mark timeout
                try:
                    if os.name != "nt":
                        os.killpg(proc.pid, signal.SIGKILL)
                    else:
                        proc.kill()
                finally:
                    try:
                        stdout, stderr = proc.communicate(timeout=0.25)
                    except Exception:
                        stdout, stderr = "", ""

                results.append({
                    "case": idx, "input": input_data, "expected": expected,
                    "stdout": stdout or "", "stderr": stderr or "",
                    "passed": False, "returncode": None, "timeout": True,
                })

                if stop_on_timeout:
                    submission_timed_out = True
                    break

    return {
        "test_style": "script",
        "total": len(cases),
        "passed": passed_count,
        "failed": (len(results) - passed_count),
        "results": results,
        "submission_timeout": submission_timed_out,
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
