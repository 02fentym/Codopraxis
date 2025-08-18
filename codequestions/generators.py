# codequestions/generators.py
from __future__ import annotations
from typing import Callable, Dict, Tuple
from .compiler import compile_question


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
        raise ValueError(f"No generator registered for language='{language}', style='{test_style}'") from e


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


# --- Optional: a minimal stub so you can smoke-test the flow now ---
@register("python", "script")
def _stub_python_script(spec: dict) -> str:
    # Replace with a real unittest generator in the next step.
    # This confirms the caching and retrieval path is working.
    cases = spec.get("test_cases", [])
    return "# stub python script runner\n# cases: " + str(len(cases)) + "\n"
