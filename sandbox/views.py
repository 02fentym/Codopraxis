# sandbox/views.py
import time, json, os, shutil, subprocess, datetime,tempfile, uuid, xml.etree.ElementTree as ET
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from codequestions.models import CodeQuestion, StructuralTest
from .models import Submission
from django.shortcuts import get_object_or_404, render, redirect


# If you used a different tag in Step 1, change here
DOCKER_IMAGE = "cp-python-runner:0.1"


def _normalize_junit_str(xml_text: str):
    if not xml_text:
        return {
            "status": "sandbox_error",
            "summary": {"tests": 0, "failures": 0, "errors": 0, "time_s": 0.0},
            "first_failure": None,
        }
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return {
            "status": "sandbox_error",
            "summary": {"tests": 0, "failures": 0, "errors": 0, "time_s": 0.0},
            "first_failure": None,
        }

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
                        "suite": suite.get("name", "") or "",
                        "test": case.get("name", "") or "",
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


def _student_payload_from_submission(sub, debug=False):
    """
    Returns a student-friendly JSON view of a Submission.
    """
    # Prefer saved XML to re-derive first_failure; fall back to saved summary/status.
    norm = _normalize_junit_str(sub.junit_xml) if sub.junit_xml else {
        "status": sub.status,
        "summary": sub.summary or {"tests": 0, "failures": 0, "errors": 0, "time_s": 0.0},
        "first_failure": None,
    }

    # Reclassify pytest-timeout signature if needed
    if norm.get("status") == "failed" and norm.get("first_failure"):
        msg = (norm["first_failure"].get("message") or "") + " " + (norm["first_failure"].get("details") or "")
        if "timeout" in msg.lower():
            norm["status"] = "timeout"

    status = norm["status"]
    tests = norm["summary"]["tests"]
    time_s = norm["summary"]["time_s"]
    first_failure = norm.get("first_failure")

    if status == "passed":
        title = "All tests passed ✅"
        message = f"Great job — {tests} test{'s' if tests != 1 else ''} passed."
    elif status == "timeout":
        title = "Timed out ⏳"
        message = "Your code exceeded the allowed time limit."
    elif status == "failed":
        title = "Some tests failed ❌"
        fail_name = first_failure["test"] if first_failure else "a test"
        message = f"First failing test: {fail_name}."
    elif status == "error":
        title = "Runtime error ⚠️"
        message = "Your code or tests crashed. Check the first error."
    else:
        title = "Sandbox issue"
        message = "We couldn’t complete your run."

    payload = {
        "id": sub.id,
        "question_id": sub.code_question_id,
        "runtime": getattr(sub.runtime, "name", None),
        "language": getattr(getattr(sub.runtime, "language", None), "name", None),
        "status": status,
        "title": title,
        "message": message,
        "stats": {
            "tests": tests,
            "failures": norm["summary"]["failures"],
            "errors": norm["summary"]["errors"],
            "time_s": time_s,
            "duration_s": sub.duration_s,
            "timeout_seconds": sub.timeout_seconds,
            "memory_limit_mb": sub.memory_limit_mb,
        },
        "created": sub.created.isoformat(),
    }

    # Include minimal failure detail for learning (not full stack)
    if first_failure:
        payload["first_failure"] = {
            "test": first_failure.get("test"),
            "message": first_failure.get("message"),
        }

    # Optional debug tails (teacher/dev)
    if debug:
        payload["debug"] = {
            "stdout_tail": sub.stdout_tail[-2000:] if sub.stdout_tail else "",
            "stderr_tail": sub.stderr_tail[-2000:] if sub.stderr_tail else "",
        }

    return payload


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
    POST JSON:
    {
      "code_question_id": 123,          # preferred path (uses DB tests)
      "runtime_id": 5,                   # optional; else choose by language or auto if single
      "language": "python",              # optional selector when multiple runtimes exist
      "student_code": "...",             # required
      "timeout_seconds": 3,              # optional override (defaults from CodeQuestion, else 5)
      "memory_limit_mb": 256             # optional override (defaults from CodeQuestion, else 256)
    }
    Fallback dev mode (if no code_question_id): pass "tests_code".
    Returns normalized JSON and never 500s for persistence errors (adds 'persistence_error').
    """
    # ---- Parse & validate payload ----
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return HttpResponseBadRequest("Invalid JSON body.")

    student_code = (payload.get("student_code") or "").strip()
    if not student_code:
        return HttpResponseBadRequest("student_code is required.")

    cq_id = payload.get("code_question_id")
    runtime_id = payload.get("runtime_id")
    lang_hint = (payload.get("language") or "").strip().lower()

    q = None
    chosen_runtime = None
    tests_code = None
    cq_timeout = None
    cq_memory = None

    # ---- Load tests from DB (preferred) ----
    if cq_id:
        try:
            q = CodeQuestion.objects.get(pk=cq_id)
        except CodeQuestion.DoesNotExist:
            return HttpResponseBadRequest("CodeQuestion not found.")

        # Only STRUCTURAL for now
        if str(getattr(q, "question_type", "")).upper() != "STRUCTURAL":
            return HttpResponseBadRequest("Only STRUCTURAL CodeQuestions are supported right now.")

        cq_timeout = getattr(q, "timeout_seconds", None)
        cq_memory  = getattr(q, "memory_limit_mb", None)

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
                available = [{"runtime_id": t.runtime_id,
                              "runtime": str(t.runtime),
                              "language": getattr(t.runtime.language, "name", "")} for t in qs]
                return JsonResponse({"error": "runtime_id has no test for this question.",
                                     "available": available}, status=400)
            chosen_runtime = match.runtime
            tests_code = match.test_source
        else:
            if lang_hint:
                match = next((t for t in qs
                              if (getattr(t.runtime.language, "name", "") or "").strip().lower() == lang_hint), None)
                if match:
                    chosen_runtime = match.runtime
                    tests_code = match.test_source
            if tests_code is None:
                if len(qs) == 1:
                    chosen_runtime = qs[0].runtime
                    tests_code = qs[0].test_source
                else:
                    available = [{"runtime_id": t.runtime_id,
                                  "runtime": str(t.runtime),
                                  "language": getattr(t.runtime.language, "name", "")} for t in qs]
                    return JsonResponse({"error": "Multiple runtime tests exist; specify runtime_id or language.",
                                         "available": available}, status=400)

        runtime_lang = (getattr(chosen_runtime.language, "name", "") or "").strip().lower()
        if runtime_lang != "python":
            return HttpResponseBadRequest("Only Python runtimes are supported at this step.")

    # ---- Dev fallback (Step 2): allow inline tests_code ----
    else:
        tests_code = (payload.get("tests_code") or "").strip()
        if not tests_code:
            return HttpResponseBadRequest("Either provide code_question_id OR tests_code.")

    # ---- Limits (payload overrides question defaults) ----
    timeout_seconds = int(payload.get("timeout_seconds") or cq_timeout or 5)
    memory_limit_mb = int(payload.get("memory_limit_mb") or cq_memory or 256)

    # ---- Workspace ----
    job_id = str(uuid.uuid4())[:8]
    workspace = tempfile.mkdtemp(prefix=f"sandbox-{job_id}-")
    report_path = os.path.join(workspace, "report.xml")

    try:
        student_dir = os.path.join(workspace, "student")
        tests_dir   = os.path.join(workspace, "tests")
        os.makedirs(student_dir, exist_ok=True)
        os.makedirs(tests_dir, exist_ok=True)

        # Student file
        with open(os.path.join(student_dir, "student.py"), "w", encoding="utf-8") as f:
            f.write(student_code)

        # Teach pytest where to import student code
        with open(os.path.join(tests_dir, "conftest.py"), "w", encoding="utf-8") as f:
            f.write('import sys; sys.path.append("/workspace/student")\n')

        # Teacher tests
        with open(os.path.join(tests_dir, "test_student.py"), "w", encoding="utf-8") as f:
            f.write(tests_code)

        # ---- Docker run ----
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

        start_ts = time.time()
        try:
            proc = subprocess.run(
                docker_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=max(2, timeout_seconds + 2),
                check=False,
                text=True,
            )
            duration = time.time() - start_ts
            stdout_tail = (proc.stdout or "")[-4000:]
            stderr_tail = (proc.stderr or "")[-4000:]
        except subprocess.TimeoutExpired as e:
            duration = time.time() - start_ts
            stdout_tail = (e.stdout or "")[-4000:]
            stderr_tail = (e.stderr or "")[-4000:]
            result = {
                "status": "timeout",
                "summary": {"tests": 0, "failures": 0, "errors": 0, "time_s": 0.0},
                "stdout_tail": stdout_tail,
                "stderr_tail": stderr_tail,
                "job_id": job_id,
                "duration_s": round(duration, 3),
            }
            # Persist (best effort) and return
            if cq_id:
                try:
                    Submission.objects.create(
                        code_question=q,
                        runtime=chosen_runtime,
                        user=request.user if request.user.is_authenticated else None,
                        job_id=job_id,
                        status=result["status"],
                        summary=result.get("summary", {}),
                        junit_xml="",  # none on host-timeout
                        stdout_tail=stdout_tail,
                        stderr_tail=stderr_tail,
                        timeout_seconds=timeout_seconds,
                        memory_limit_mb=memory_limit_mb,
                        duration_s=result["duration_s"],
                        student_code=student_code,
                    )
                except Exception as pe:
                    result["persistence_error"] = f"{type(pe).__name__}: {pe}"
            return JsonResponse(result, status=200)

        # ---- Parse JUnit (container completed) ----
        def _normalize_junit(path: str):
            if not os.path.exists(path):
                return {
                    "status": "sandbox_error",
                    "summary": {"tests": 0, "failures": 0, "errors": 0, "time_s": 0.0},
                    "message": "JUnit report not found."
                }
            tree = ET.parse(path)
            root = tree.getroot()
            suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
            total_tests = total_failures = total_errors = 0
            total_time = 0.0
            first_failure = None

            def as_float(x, default=0.0):
                try: return float(x)
                except Exception: return default

            for suite in suites:
                total_tests    += int(suite.get("tests", 0))
                total_failures += int(suite.get("failures", 0))
                total_errors   += int(suite.get("errors", 0))
                total_time     += as_float(suite.get("time", 0.0))
                if first_failure is None:
                    for case in suite.findall("testcase"):
                        failure = case.find("failure")
                        error   = case.find("error")
                        if failure is not None or error is not None:
                            node = failure if failure is not None else error
                            first_failure = {
                                "suite": suite.get("name", "") or "",
                                "test": case.get("name", "") or "",
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

        result = _normalize_junit(report_path)

        # Reclassify pytest-timeout signatures as timeout
        ff = result.get("first_failure")
        if result.get("status") == "failed" and ff:
            msg = (ff.get("message") or "") + " " + (ff.get("details") or "")
            if "timeout" in msg.lower():
                result["status"] = "timeout"

        # Read raw JUnit for storage
        try:
            with open(report_path, "r", encoding="utf-8", errors="replace") as f:
                junit_xml = f.read()
        except Exception:
            junit_xml = ""

        # Enrich response
        result["stdout_tail"] = stdout_tail
        result["stderr_tail"] = stderr_tail
        result["job_id"] = job_id
        result["duration_s"] = round(duration, 3)

        # Persist (best effort) and attach metadata
        if cq_id:
            try:
                submission = Submission.objects.create(
                    code_question=q,
                    runtime=chosen_runtime,
                    user=request.user if request.user.is_authenticated else None,
                    job_id=job_id,
                    status=result["status"],
                    summary=result.get("summary", {}),
                    junit_xml=junit_xml,
                    stdout_tail=stdout_tail,
                    stderr_tail=stderr_tail,
                    timeout_seconds=timeout_seconds,
                    memory_limit_mb=memory_limit_mb,
                    duration_s=result["duration_s"],
                    student_code=student_code,
                )
                result["submission_id"] = submission.id
                result["question_id"] = cq_id
                if chosen_runtime:
                    result["runtime"] = {
                        "id": getattr(chosen_runtime, "id", None),
                        "name": getattr(chosen_runtime, "name", ""),
                        "language": getattr(chosen_runtime.language, "name", ""),
                    }
            except Exception as pe:
                result["persistence_error"] = f"{type(pe).__name__}: {pe}"

        return JsonResponse(result, status=200)

    finally:
        shutil.rmtree(workspace, ignore_errors=True)


@require_GET
def submission_result(request, submission_id: int):
    """
    GET /sandbox/submission/<id>/?debug=1
    Returns a student-friendly JSON payload for a stored Submission.
    """
    sub = get_object_or_404(Submission, pk=submission_id)
    # TODO: add permission check so only the owner/teacher can view
    debug = request.GET.get("debug") in {"1", "true", "yes"}
    payload = _student_payload_from_submission(sub, debug=debug)
    return JsonResponse(payload, status=200)


@require_GET
def submission_page(request, submission_id: int):
    # Simple template that fetches JSON from /sandbox/submission/<id>/
    return render(request, "sandbox/submission_page.html", {"submission_id": submission_id})


@csrf_exempt
@require_POST
def submit_code(request):
    """
    Form-friendly endpoint.
    Expects POST form fields:
      - code_question_id (int)
      - student_code (str)
      - language (optional, e.g., 'python')
      - runtime_id (optional, picks exact runtime)
      - timeout_seconds (optional)
      - memory_limit_mb (optional)
    Redirects to: /sandbox/submission/<id>/view/
    """
    # 1) Read form fields
    cq_id = request.POST.get("code_question_id")
    student_code = (request.POST.get("student_code") or "").strip()
    lang_hint = (request.POST.get("language") or "").strip().lower()
    runtime_id = request.POST.get("runtime_id")
    timeout_seconds = request.POST.get("timeout_seconds")
    memory_limit_mb = request.POST.get("memory_limit_mb")

    if not cq_id or not student_code:
        return HttpResponseBadRequest("code_question_id and student_code are required.")

    runtime_id = int(runtime_id) if runtime_id else None
    timeout_seconds = int(timeout_seconds) if timeout_seconds else None
    memory_limit_mb = int(memory_limit_mb) if memory_limit_mb else None

    # 2) Load question + tests (Python only for now)
    q = get_object_or_404(CodeQuestion, pk=cq_id)
    if str(getattr(q, "question_type", "")).upper() != "STRUCTURAL":
        return HttpResponseBadRequest("Only STRUCTURAL CodeQuestions are supported right now.")

    # pick StructuralTest (by runtime_id, by language, or auto if only one)
    qs = (StructuralTest.objects
          .filter(code_question=q)
          .select_related("runtime", "runtime__language")
          .order_by("runtime_id"))
    if not qs:
        return HttpResponseBadRequest("No StructuralTest rows found for this CodeQuestion.")

    chosen = None
    if runtime_id:
        chosen = next((t for t in qs if t.runtime_id == runtime_id), None)
        if not chosen:
            return HttpResponseBadRequest("runtime_id has no test for this question.")
    elif lang_hint:
        chosen = next((t for t in qs
                       if (getattr(t.runtime.language, "name", "") or "").strip().lower() == lang_hint), None)
        if not chosen and len(qs) == 1:
            chosen = qs[0]
    else:
        chosen = qs[0] if len(qs) == 1 else None

    if not chosen:
        return HttpResponseBadRequest("Multiple runtimes exist; pass runtime_id or language.")

    runtime = chosen.runtime
    runtime_lang = (getattr(runtime.language, "name", "") or "").strip().lower()
    if runtime_lang != "python":
        return HttpResponseBadRequest("Only Python runtimes are supported at this step.")

    tests_code = chosen.test_source

    # 3) Resolve limits (form override -> question defaults -> fallback)
    timeout_seconds = int(timeout_seconds or getattr(q, "timeout_seconds", 5) or 5)
    memory_limit_mb = int(memory_limit_mb or getattr(q, "memory_limit_mb", 256) or 256)

    # 4) Create temp workspace and run container
    job_id = str(uuid.uuid4())[:8]
    workspace = tempfile.mkdtemp(prefix=f"sandbox-{job_id}-")
    report_path = os.path.join(workspace, "report.xml")

    try:
        os.makedirs(os.path.join(workspace, "student"), exist_ok=True)
        os.makedirs(os.path.join(workspace, "tests"), exist_ok=True)
        with open(os.path.join(workspace, "student", "student.py"), "w", encoding="utf-8") as f:
            f.write(student_code)
        with open(os.path.join(workspace, "tests", "conftest.py"), "w", encoding="utf-8") as f:
            f.write('import sys; sys.path.append("/workspace/student")\n')
        with open(os.path.join(workspace, "tests", "test_student.py"), "w", encoding="utf-8") as f:
            f.write(tests_code)

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

        start_ts = time.time()
        try:
            proc = subprocess.run(
                docker_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=max(2, timeout_seconds + 2),
                check=False,
                text=True,
            )
            duration = time.time() - start_ts
            stdout_tail = (proc.stdout or "")[-4000:]
            stderr_tail = (proc.stderr or "")[-4000:]
        except subprocess.TimeoutExpired as e:
            duration = time.time() - start_ts
            stdout_tail = (e.stdout or "")[-4000:]
            stderr_tail = (e.stderr or "")[-4000:]
            # Save timeout Submission and redirect
            submission = Submission.objects.create(
                code_question=q,
                runtime=runtime,
                user=request.user if request.user.is_authenticated else None,
                job_id=job_id,
                status="timeout",
                summary={"tests": 0, "failures": 0, "errors": 0, "time_s": 0.0},
                junit_xml="",
                stdout_tail=stdout_tail,
                stderr_tail=stderr_tail,
                timeout_seconds=timeout_seconds,
                memory_limit_mb=memory_limit_mb,
                duration_s=round(duration, 3),
                student_code=student_code,
            )
            return redirect("sandbox-submission-page", submission_id=submission.id)

        # Parse JUnit
        def _normalize_junit_file(p):
            if not os.path.exists(p):
                return {"status": "sandbox_error",
                        "summary": {"tests": 0, "failures": 0, "errors": 0, "time_s": 0.0},
                        "first_failure": None}
            tree = ET.parse(p)
            root = tree.getroot()
            suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
            total_tests = total_failures = total_errors = 0
            total_time = 0.0
            first_failure = None

            def as_float(x, d=0.0):
                try: return float(x)
                except Exception: return d

            for suite in suites:
                total_tests    += int(suite.get("tests", 0))
                total_failures += int(suite.get("failures", 0))
                total_errors   += int(suite.get("errors", 0))
                total_time     += as_float(suite.get("time", 0.0))
                if first_failure is None:
                    for case in suite.findall("testcase"):
                        failure = case.find("failure")
                        error   = case.find("error")
                        if failure is not None or error is not None:
                            node = failure if failure is not None else error
                            first_failure = {
                                "suite": suite.get("name", "") or "",
                                "test": case.get("name", "") or "",
                                "message": (node.get("message", "") or "")[:2000],
                                "type": node.get("type", "") or "",
                                "time_s": as_float(case.get("time", 0.0)),
                                "details": (node.text or "")[:4000],
                            }
                            break

            status = "passed"
            if total_errors > 0: status = "error"
            elif total_failures > 0: status = "failed"

            return {
                "status": status,
                "summary": {"tests": total_tests, "failures": total_failures, "errors": total_errors, "time_s": total_time},
                "first_failure": first_failure,
            }

        result = _normalize_junit_file(report_path)

        # Reclassify pytest-timeout signatures
        if result.get("status") == "failed" and result.get("first_failure"):
            msg = (result["first_failure"].get("message") or "") + " " + (result["first_failure"].get("details") or "")
            if "timeout" in msg.lower():
                result["status"] = "timeout"

        # read XML for storage
        try:
            with open(report_path, "r", encoding="utf-8", errors="replace") as f:
                junit_xml = f.read()
        except Exception:
            junit_xml = ""

        submission = Submission.objects.create(
            code_question=q,
            runtime=runtime,
            user=request.user if request.user.is_authenticated else None,
            job_id=job_id,
            status=result["status"],
            summary=result.get("summary", {}),
            junit_xml=junit_xml,
            stdout_tail=stdout_tail,
            stderr_tail=stderr_tail,
            timeout_seconds=timeout_seconds,
            memory_limit_mb=memory_limit_mb,
            duration_s=round(duration, 3),
            student_code=student_code,
        )
        return redirect("sandbox-submission-page", submission_id=submission.id)

    finally:
        shutil.rmtree(workspace, ignore_errors=True)
