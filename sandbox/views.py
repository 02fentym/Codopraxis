# sandbox/views.py
import json
import os
import shutil
import subprocess
import tempfile
import uuid
import xml.etree.ElementTree as ET

from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

# If you used a different tag in Step 1, change here
DOCKER_IMAGE = "cp-python-runner:0.1"

# STEP 3: imports from your apps
from codequestions.models import CodeQuestion, StructuralTest

def _normalize_junit(report_path: str):
    if not os.path.exists(report_path):
        return {
            "status": "sandbox_error",
            "summary": {"tests": 0, "failures": 0, "errors": 0, "time_s": 0.0},
            "message": "JUnit report not found."
        }

    tree = ET.parse(report_path)
    root = tree.getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))

    total_tests = total_failures = total_errors = 0
    total_time = 0.0
    first_failure = None

    def as_float(x, default=0.0):
        try:
            return float(x)
        except Exception:
            return default

    for suite in suites:
        total_tests += int(suite.get("tests", 0))
        total_failures += int(suite.get("failures", 0))
        total_errors += int(suite.get("errors", 0))
        total_time += as_float(suite.get("time", 0.0))
        if first_failure is None:
            for case in suite.findall("testcase"):
                failure = case.find("failure")
                error = case.find("error")
                if failure is not None or error is not None:
                    node = failure if failure is not None else error
                    first_failure = {
                        "suite": suite.get("name", ""),
                        "test": case.get("name", ""),
                        "message": (node.get("message", "") or "")[:2000],
                        "type": node.get("type", "") or "",
                        "time_s": as_float(case.get("time", 0.0)),
                        "details": (node.text or "")[:4000],
                    }
                    break

    if total_errors > 0:
        status = "error"
    elif total_failures > 0:
        status = "failed"
    else:
        status = "passed"

    return {
        "status": status,
        "summary": {
            "tests": total_tests,
            "failures": total_failures,
            "errors": total_errors,
            "time_s": total_time,
        },
        "first_failure": first_failure,
    }

@csrf_exempt
@require_POST
def run_code(request):
    """
    POST JSON (Step 3):
    {
      "code_question_id": 123,                 # preferred in Step 3
      "runtime_id": 5,                         # optional (choose this test)
      "language": "python",                    # optional fallback selector
      "student_code": "...required...",        # student code string
      "timeout_seconds": 3,                    # optional override, else from CodeQuestion
      "memory_limit_mb": 256                   # optional override, else from CodeQuestion
    }

    For backward-compat (Step 2):
      If code_question_id is NOT provided, we still accept "tests_code" (inline).
    """
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return HttpResponseBadRequest("Invalid JSON body.")

    # Always required
    student_code = (payload.get("student_code") or "").strip()
    if not student_code:
        return HttpResponseBadRequest("student_code is required.")

    # Defaults if we end up using a CodeQuestion
    cq_timeout = None
    cq_memory = None
    tests_code = None
    chosen_runtime = None
    lang_hint = (payload.get("language") or "").strip().lower()
    runtime_id = payload.get("runtime_id")
    cq_id = payload.get("code_question_id")

    # STEP 3: prefer tests from DB when code_question_id is provided
    if cq_id:
        try:
            q = CodeQuestion.objects.get(pk=cq_id)
        except CodeQuestion.DoesNotExist:
            return HttpResponseBadRequest("CodeQuestion not found.")

        # Must be structural for now
        if getattr(q, "question_type", "").upper() != "STRUCTURAL":
            return HttpResponseBadRequest("Only STRUCTURAL CodeQuestions are supported in Step 3.")

        cq_timeout = getattr(q, "timeout_seconds", None)
        cq_memory = getattr(q, "memory_limit_mb", None)

        qs = (
            StructuralTest.objects
            .filter(code_question=q)
            .select_related("runtime", "runtime__language")
            .order_by("runtime_id")
        )
        if not qs:
            return HttpResponseBadRequest("No StructuralTest rows found for this CodeQuestion.")

        if runtime_id:
            match = next((t for t in qs if t.runtime_id == runtime_id), None)
            if not match:
                available = [{"runtime_id": t.runtime_id, "runtime": str(t.runtime)} for t in qs]
                return JsonResponse(
                    {"error": "runtime_id has no test for this question.", "available": available},
                    status=400
                )
            chosen_runtime = match.runtime
            tests_code = match.test_source
        else:
            # try language hint
            if lang_hint:
                match = next((t for t in qs if (t.runtime.language.name or "").strip().lower() == lang_hint), None)
                if match:
                    chosen_runtime = match.runtime
                    tests_code = match.test_source
            # fallback: auto-pick if exactly one runtime test
            if tests_code is None:
                if len(qs) == 1:
                    chosen_runtime = qs[0].runtime
                    tests_code = qs[0].test_source
                else:
                    available = [
                        {
                            "runtime_id": t.runtime_id,
                            "runtime": str(t.runtime),
                            "language": getattr(t.runtime.language, "name", ""),
                        }
                        for t in qs
                    ]
                    return JsonResponse(
                        {"error": "Multiple runtime tests exist; specify runtime_id or language.", "available": available},
                        status=400
                    )

        # Python-only enforcement for Step 3
        runtime_lang = (getattr(chosen_runtime.language, "name", "") or "").strip().lower()
        if runtime_lang != "python":
            return HttpResponseBadRequest("Only Python runtimes are supported in Step 3.")

    else:
        # Backward-compat (Step 2 mode): accept inline tests_code
        tests_code = (payload.get("tests_code") or "").strip()
        if not tests_code:
            return HttpResponseBadRequest("Either provide code_question_id OR tests_code.")

    # Resolve limits (payload overrides question defaults)
    timeout_seconds = int(payload.get("timeout_seconds") or cq_timeout or 5)
    memory_limit_mb = int(payload.get("memory_limit_mb") or cq_memory or 256)

    # Create a temp workspace
    job_id = str(uuid.uuid4())[:8]
    workspace = tempfile.mkdtemp(prefix=f"sandbox-{job_id}-")
    report_path = os.path.join(workspace, "report.xml")

    try:
        # Filesystem layout
        student_dir = os.path.join(workspace, "student")
        tests_dir = os.path.join(workspace, "tests")
        os.makedirs(student_dir, exist_ok=True)
        os.makedirs(tests_dir, exist_ok=True)

        # Student code
        with open(os.path.join(student_dir, "student.py"), "w", encoding="utf-8") as f:
            f.write(student_code)

        # Always add a tiny conftest to make student import path available
        with open(os.path.join(tests_dir, "conftest.py"), "w", encoding="utf-8") as f:
            f.write('import sys; sys.path.append("/workspace/student")\n')

        # Teacher tests (from DB or inline)
        with open(os.path.join(tests_dir, "test_student.py"), "w", encoding="utf-8") as f:
            f.write(tests_code)

        # Docker command
        docker_cmd = [
            "docker", "run", "--rm",
            "--network=none",
            f"--memory={memory_limit_mb}m",
            "--cpus=1.0",
            "--pids-limit=256",
            "--read-only",
            "-v", f"{workspace}:/workspace:rw",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m",
            "--security-opt", "no-new-privileges",
            "--cap-drop", "ALL",
            "-e", f"RUN_TIMEOUT={timeout_seconds}",
            "-e", "REPORT_PATH=/workspace/report.xml",
            DOCKER_IMAGE,
        ]

        host_timeout = max(2, timeout_seconds + 2)
        try:
            proc = subprocess.run(
                docker_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=host_timeout,
                check=False,
                text=True,
            )
            stdout_tail = proc.stdout[-4000:] if proc.stdout else ""
            stderr_tail = proc.stderr[-4000:] if proc.stderr else ""
            result = _normalize_junit(report_path)
        except subprocess.TimeoutExpired as e:
            result = {"status": "timeout", "summary": {"tests": 0, "failures": 0, "errors": 0, "time_s": 0.0}}
            stdout_tail = (e.stdout or "")[-4000:]
            stderr_tail = (e.stderr or "")[-4000:]

        # Reclassify pytest-timeout as timeout
        ff = result.get("first_failure")
        if result.get("status") == "failed" and ff:
            msg = (ff.get("message") or "") + " " + (ff.get("details") or "")
            if "timeout" in msg.lower():
                result["status"] = "timeout"

        result["stdout_tail"] = stdout_tail
        result["stderr_tail"] = stderr_tail
        result["job_id"] = job_id

        # Nice metadata when using DB mode
        if cq_id:
            result["question_id"] = cq_id
            if chosen_runtime:
                result["runtime"] = {
                    "id": getattr(chosen_runtime, "id", None),
                    "name": getattr(chosen_runtime, "name", ""),
                    "language": getattr(chosen_runtime.language, "name", ""),
                }

        return JsonResponse(result, status=200)
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
