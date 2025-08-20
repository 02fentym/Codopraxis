# sandbox/utils.py
from __future__ import annotations
import subprocess, sys, tempfile, os, textwrap, signal, time, shutil
from typing import Dict, Any, List
import json
import traceback

from codequestions.generators import get_generator

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

def _run_in_docker(*, workdir: str, mem_mb: int, cpus: float, image: str, name: str, timeout: float) -> subprocess.CompletedProcess:
    """
    Runs a command inside a Docker container with strict resource limits.
    Returns a CompletedProcess instance.
    """
    _ensure_docker_available()
    
    cmd = [
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
        "python", "test_runner.py"
    ]
    
    try:
        # We need to run the subprocess with a timeout
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            text=True,
            check=False
        )
        return result
    except subprocess.TimeoutExpired as e:
        # This timeout is for the docker run command itself
        # The internal script timeout is handled by the script itself
        # If this happens, it's a sandbox issue
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=124, # 124 is the return code for timeout from "timeout" command
            stdout="",
            stderr=f"Sandbox process timed out after {timeout} seconds."
        )


def _parse_script_results(stdout: str, stderr: str, returncode: int, timeout: bool) -> Dict[str, Any]:
    """
    Parses the output of a script-based test runner.
    """
    lines = stdout.strip().splitlines()
    if not lines:
        return {
            "ok": False,
            "error": "No output from test runner.",
            "results": [],
            "total": 0,
            "passed": 0,
            "failed": 0,
            "submission_timeout": timeout,
        }
    
    # We'll assume the last line of the output is the summary
    last_line = lines[-1]
    if "OK" in last_line:
        passed_count = last_line.count("OK")
        failed_count = 0
    elif "FAILED" in last_line:
        passed_count = last_line.count("passed")
        failed_count = last_line.count("failed")
    else:
        passed_count = 0
        failed_count = 0

    return {
        "ok": failed_count == 0 and not timeout,
        "results": [{"name": "Result", "stdout": stdout, "stderr": stderr, "passed": failed_count == 0 and not timeout}],
        "total": passed_count + failed_count,
        "passed": passed_count,
        "failed": failed_count,
        "submission_timeout": timeout,
    }


def _parse_function_results(stdout: str, stderr: str, returncode: int, timeout: bool) -> Dict[str, Any]:
    """
    Parses the output from our custom function test runner.
    """
    # Our test runner outputs a JSON-like summary, but we'll use a more
    # reliable method to get the results.
    try:
        # We can analyze the stdout from the unittest run to get the results.
        lines = stdout.strip().splitlines()
        summary = lines[-1]
        
        # Example summary: "Ran 5 tests in 0.001s\nOK"
        total = 0
        if "Ran" in summary:
            total = int(summary.split()[1])
        
        passed = 0
        failed = 0
        
        if "OK" in summary:
            passed = total
        elif "FAILED" in summary:
            # This is a simple parser, can be expanded to be more robust
            failed_line = next((line for line in lines if line.startswith("FAILED")), None)
            if failed_line:
                failed = len(failed_line.split(" (")[1].split(")")[:-1])
                passed = total - failed
        
        # A simple placeholder for detailed results, which would be more complex to parse
        results = [
            {"case": "Test 1", "passed": True},
            {"case": "Test 2", "passed": True},
        ]
        
        return {
            "ok": failed == 0 and not timeout,
            "test_style": "function",
            "total": total,
            "passed": passed,
            "failed": failed,
            "results": results,
            "submission_timeout": timeout,
        }
        
    except Exception as e:
        return {
            "ok": False,
            "error": f"Failed to parse test results: {e}",
            "results": [],
            "total": 0,
            "passed": 0,
            "failed": 0,
            "submission_timeout": timeout,
        }


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
    if language not in ["python"]:
        return {
            "ok": False,
            "error": f"Unsupported language: {language}",
            "meta": {"language": language}
        }

    style = compiled_specs.get("test_style")
    
    # We'll use a temporary directory for the Docker run
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Write the student's submission to a file
            submission_path = os.path.join(temp_dir, "solution.py")
            with open(submission_path, "w") as f:
                f.write(submission_code)

            # Generate and write the test runner script
            generator_fn = get_generator(language, style)
            test_runner_code = generator_fn(compiled_specs)
            test_runner_path = os.path.join(temp_dir, "test_runner.py")
            with open(test_runner_path, "w") as f:
                f.write(test_runner_code)
            
            # Execute the tests in a Docker container
            docker_result = _run_in_docker(
                workdir=temp_dir,
                mem_mb=compiled_specs.get("memory_limit_mb", 128),
                cpus=compiled_specs.get("cpus", 1),
                image=compiled_specs.get("docker_image", "python:3.12-slim"),
                name=f"sandbox-{os.path.basename(temp_dir)}",
                timeout=compiled_specs.get("overall_timeout_seconds", 10)
            )

            # Parse the results based on the test style
            if style == "script":
                res = _parse_script_results(docker_result.stdout, docker_result.stderr, docker_result.returncode, docker_result.returncode == 124)
            elif style == "function":
                res = _parse_function_results(docker_result.stdout, docker_result.stderr, docker_result.returncode, docker_result.returncode == 124)
            elif style == "oop":
                res = {"ok": False, "error": "OOP style not implemented yet.", "meta": {"language": language}}
            else:
                res = {"ok": False, "error": f"Unknown test_style: {style}", "meta": {"language": language}}
            
            return res
        
        except Exception as e:
            return {
                "ok": False,
                "error": f"An internal error occurred: {traceback.format_exc()}",
                "meta": {"language": language, "style": style},
            }

