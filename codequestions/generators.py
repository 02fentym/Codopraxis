# codequestions/generators.py
from __future__ import annotations
from typing import Callable, Dict, Tuple, Any, List
from textwrap import indent

from .compiler import compile_question

# ---------------- Registry ----------------

GeneratorFn = Callable[[dict], str]  # input: compiled_spec, output: runner source
_registry: Dict[Tuple[str, str], GeneratorFn] = {}  # (language, test_style) -> fn


def register(language: str, test_style: str):
    """Decorator to register a generator function for (language, style)."""
    key = (language, test_style)

    def _wrap(fn: GeneratorFn) -> GeneratorFn:
        _registry[key] = fn
        return fn

    return _wrap


def get_generator(language: str, test_style: str) -> GeneratorFn:
    try:
        return _registry[(language, test_style)]
    except KeyError as e:
        raise ValueError(
            f"No generator registered for language='{language}', style='{test_style}'"
        ) from e


# --------------- Cache helper ---------------

def get_or_build_runner(question, language: str, generator_version: str = "1") -> str:
    """
    Return cached runner source for (question, language) if fresh; otherwise build, cache, and return.
    Freshness is based on question.compiled_version and the supplied generator_version.
    """
    # Ensure we have a compiled_spec snapshot
    if not question.compiled_spec or question.compiled_spec.get("test_style") != question.test_style:
        compile_question(question)

    cache = question.compiled_runner_cache or {}
    entry = cache.get(language)

    if (
        entry
        and entry.get("version") == question.compiled_version
        and entry.get("generator_version") == generator_version
        and "content" in entry
    ):
        return entry["content"]

    # Build with the registered generator for (language, style)
    gen = get_generator(language, question.test_style)
    content = gen(question.compiled_spec)

    # Save back to the per-language cache
    cache[language] = {
        "version": question.compiled_version,
        "generator_version": generator_version,
        "content": content,
    }
    question.compiled_runner_cache = cache
    question.save(update_fields=["compiled_runner_cache"])
    return content


# --------------- Real Python generator (script → unittest) ---------------

@register("python", "script")
def python_script_unittest(spec: dict) -> str:
    """
    Build a Python unittest file that runs solution.py as a script via subprocess,
    feeds stdin, and asserts exact stdout per case (including trailing newlines).

    Expected spec shape:
    {
      "test_style": "script",
      "test_cases": [{"input": "...", "output": "..."}, ...]
    }
    """
    cases: List[Dict[str, Any]] = spec.get("test_cases", [])
    if not cases:
        raise ValueError("No test_cases provided for script style")
    
    timeout = int(spec.get("timeout_seconds", 5))

    methods: List[str] = []
    for i, case in enumerate(cases, start=1):
        stdin = case.get("input", "")
        expected = case.get("output")
        if expected is None:
            raise ValueError(f"script case #{i} missing required 'output'")

        method = f"""
def test_case_{i}(self):
    input_data = {stdin!r}
    expected = {expected!r}
    proc = subprocess.run(
        [sys.executable, "-u", "solution.py"],
        input=input_data.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=self.TIMEOUT,
        check=False,
    )
    stdout = proc.stdout.decode("utf-8", errors="replace")
    self.assertEqual(
        expected,
        stdout,
        msg=f"Case {i}: expected exact stdout match.\\nSTDERR:\\n{{proc.stderr.decode('utf-8', errors='replace')}}"
    )
"""
        methods.append(indent(method, "    "))

    body = "\n".join(methods)

    return f"""# AUTO-GENERATED: python script runner
# Do not edit by hand; changes will be overwritten when the question is recompiled.
import sys, subprocess, unittest


class ScriptTests(unittest.TestCase):
    TIMEOUT = {timeout}  # seconds

{body}

if __name__ == "__main__":
    unittest.main(verbosity=2)
"""
