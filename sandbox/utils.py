# sandbox/utils.py
from __future__ import annotations
import subprocess, sys, tempfile, os, textwrap, signal, time, shutil
from typing import Dict, Any, List


def _ensure_docker_available() -> None:
    """Fail fast if Docker CLI is missing."""
    if shutil.which("docker") is None:
        raise RuntimeError("Docker is required to run submissions safely, but 'docker' was not found on PATH.")
    # Optional lightweight ping
    try:
        subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=2, check=False
        )
    except Exception:
        # Don't hard-fail on slow startups; the actual run will surface errors.
        pass


def _docker_cmd(*, workdir: str, mem_mb: int, cpus: float, image: str, name: str) -> List[str]:
    return [
        "docker", "run", "--rm", "-i",           # <-- add -i
        "--name", name,
        "--network=none",
        "--cpus", str(cpus),
        f"--memory={mem_mb}m", f"--memory-swap={mem_mb}m",
        "--pids-limit", "64",
        "--read-only",
        "--cap-drop=ALL", "--security-opt", "no-new-privileges",
        "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=64m",
        "-v", f"{workdir}:/workspace:ro",
        "-w", "/workspace",
        image,
        "python", "-u", "-B", "solution.py",
    ]



def _docker_kill(name: str) -> None:
    """Best-effort: kill & remove the container if it outlives the client on timeout."""
    try:
        subprocess.run(["docker", "rm", "-f", name], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=2)
    except Exception:
        pass


def run_script_tests(compiled_specs: Dict[str, Any], submission_code: str) -> Dict[str, Any]:
    assert compiled_specs.get("test_style") == "script", "This runner only supports test_style='script'."

    _ensure_docker_available()

    cases: List[Dict[str, Any]] = compiled_specs.get("test_cases", [])
    case_timeout = float(compiled_specs.get("timeout_seconds", 5))
    # New knobs (safe defaults)
    overall_cap = float(compiled_specs.get("overall_timeout_seconds", case_timeout * 2))
    stop_on_timeout = bool(compiled_specs.get("stop_on_timeout", True))

    # Sandbox knobs (overridable per compiled spec)
    mem_mb = int(compiled_specs.get("memory_limit_mb", 128))
    cpus = float(compiled_specs.get("cpus", 1))
    docker_image = str(compiled_specs.get("docker_image", "python:3.12-slim"))

    submission_start = time.monotonic()

    def submission_time_left() -> float:
        return max(0.0, overall_cap - (time.monotonic() - submission_start))

    submission_timed_out = False
    results: List[Dict[str, Any]] = []
    passed_count = 0

    # Write solution once per submission; mount read-only into the container.
    with tempfile.TemporaryDirectory() as td:
        solution_path = os.path.join(td, "solution.py")
        with open(solution_path, "w", encoding="utf-8") as f:
            f.write(textwrap.dedent(submission_code).lstrip())

        for idx, case in enumerate(cases, start=1):
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
            this_timeout = min(case_timeout, submission_time_left())

            # Unique, DNS-safe container name: cq-<pid>-<ms>-<idx>
            container_name = f"cq-{os.getpid()}-{int(time.time() * 1000)}-{idx}"

            try:
                cmd = _docker_cmd(workdir=td, mem_mb=mem_mb, cpus=cpus, image=docker_image, name=container_name)
                proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                stdout, stderr = proc.communicate(input=input_data, timeout=this_timeout)
                ok = (stdout == expected and proc.returncode == 0)

                results.append({
                    "case": idx, "input": input_data, "expected": expected,
                    "stdout": stdout, "stderr": stderr,
                    "passed": ok, "returncode": proc.returncode, "timeout": False,
                })
                if ok:
                    passed_count += 1

            except subprocess.TimeoutExpired:
                # Kill container and mark timeout
                _docker_kill(container_name)
                try:
                    # Drain any remaining pipes quickly
                    stdout, stderr = proc.communicate(timeout=0.25)  # type: ignore[name-defined]
                except Exception:
                    stdout, stderr = "", ""

                results.append({
                    "case": idx, "input": input_data, "expected": expected,
                    "stdout": stdout or "", "stderr": (stderr or "") + "\n[Timed out]",
                    "passed": False, "returncode": None, "timeout": True,
                })

                if stop_on_timeout:
                    submission_timed_out = True
                    break

            except FileNotFoundError as e:
                # e.g., Docker CLI missing
                results.append({
                    "case": idx, "input": input_data, "expected": expected,
                    "stdout": "", "stderr": f"Docker not available: {e}",
                    "passed": False, "returncode": None, "timeout": False,
                })
                break

            except Exception as e:
                # Catch-all for sandbox launcher errors
                results.append({
                    "case": idx, "input": input_data, "expected": expected,
                    "stdout": "", "stderr": f"Sandbox error: {e}",
                    "passed": False, "returncode": None, "timeout": False,
                })
                if stop_on_timeout:
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
        return {"ok": False, "error": "Function style not implemented yet.", "meta": {"language": language}}
    elif style == "oop":
        return {"ok": False, "error": "OOP style not implemented yet.", "meta": {"language": language}}
    else:
        return {"ok": False, "error": f"Unknown test_style: {style}", "meta": {"language": language}}

    res["ok"] = (res.get("failed", 0) == 0)
    res["meta"] = {"language": language}
    return res
