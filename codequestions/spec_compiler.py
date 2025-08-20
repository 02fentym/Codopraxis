# codequestions/spec_compiler.py
from __future__ import annotations

from typing import Any, Dict, List, Tuple
import re

import yaml


class SpecError(ValueError):
    """Validation/normalization error with a helpful path + message."""

    def __init__(self, message: str, path: str | None = None):
        self.path = path
        super().__init__(f"{path}: {message}" if path else message)


# ---------- Public API ----------

def compile_yaml_to_spec(yaml_text: str, *, schema_version: int = 1) -> Dict[str, Any]:
    """
    Parse and validate a single problem YAML, and return a normalized compiled_spec dict.

    - Enforces single-document YAML
    - Validates top-level structure
    - Normalizes per type (standardIo | function | oop)
    - Returns a stable dict suitable for CodeQuestion.compiled_spec
    """
    raw = _parse_single_yaml(yaml_text)
    _require_type(raw)
    _require_desc(raw)

    t = raw["type"]
    if t == "standardIo":
        tests = _normalize_standard_io_tests(raw)
        compiled = {
            "schema_version": schema_version,
            "type": "standardIo",
            "description": _as_str(raw.get("description"), "description"),
            "tests": tests,
        }
    elif t == "function":
        fn = _normalize_function_signature(raw)
        tests = _normalize_function_tests(raw, fn)
        compiled = {
            "schema_version": schema_version,
            "type": "function",
            "description": _as_str(raw.get("description"), "description"),
            "function": fn,
            "tests": tests,
        }
    elif t == "oop":
        klass = _normalize_class_signature(raw)
        tests = _normalize_oop_tests(raw, klass)
        compiled = {
            "schema_version": schema_version,
            "type": "oop",
            "description": _as_str(raw.get("description"), "description"),
            "class": klass,
            "tests": tests,
        }
    else:
        raise SpecError("Unsupported type; expected one of: standardIo, function, oop", "type")

    _reject_unknown_top_level_keys(
        raw,
        allowed={"type", "description", "tests", "function", "class"},
    )
    return compiled


# ---------- Parsing helpers ----------

def _parse_single_yaml(yaml_text: str) -> Dict[str, Any]:
    try:
        # detect multiple documents (--- ... --- ...)
        docs = list(yaml.safe_load_all(yaml_text))
    except yaml.YAMLError as e:
        raise SpecError(f"YAML parse error: {e}") from e

    if len(docs) == 0:
        raise SpecError("YAML is empty")
    if len(docs) > 1:
        raise SpecError("Multiple YAML documents found; upload exactly one problem per file")

    data = docs[0]
    if not isinstance(data, dict):
        raise SpecError("Top-level YAML must be a mapping (key/value object)")
    return data


def _require_type(raw: Dict[str, Any]) -> None:
    if "type" not in raw:
        raise SpecError("Missing required key", "type")
    if raw["type"] not in {"standardIo", "function", "oop"}:
        raise SpecError("Must be one of: standardIo, function, oop", "type")


def _require_desc(raw: Dict[str, Any]) -> None:
    desc = raw.get("description")
    if not isinstance(desc, str) or not desc.strip():
        raise SpecError("description must be a non-empty string", "description")


def _reject_unknown_top_level_keys(raw: Dict[str, Any], *, allowed: set[str]) -> None:
    for k in raw.keys():
        if k not in allowed:
            raise SpecError(f"Unknown top-level key '{k}'", k)


# ---------- Type: standardIo ----------

def _normalize_standard_io_tests(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    tests = _require_tests_list(raw)

    norm: List[Dict[str, Any]] = []
    for i, t in enumerate(tests):
        path = f"tests[{i}]"
        if not isinstance(t, dict):
            raise SpecError("Each test must be a mapping", path)

        name = _require_name(t, path)
        if "stdout" not in t:
            raise SpecError("Missing required key 'stdout'", f"{path}.stdout")

        stdin = t.get("stdin", "")
        stdout = t["stdout"]

        stdin_s = _as_str(stdin, f"{path}.stdin")
        stdout_s = _as_str(stdout, f"{path}.stdout")

        # Normalize newlines and ensure stdout ends with '\n'
        stdin_s = _normalize_newlines(stdin_s)
        stdout_s = _normalize_newlines(stdout_s)
        if not stdout_s.endswith("\n"):
            stdout_s += "\n"

        _reject_unknown_keys(t, allowed={"name", "stdin", "stdout"}, path=path)

        norm.append({"name": name, "stdin": stdin_s, "stdout": stdout_s})
    _require_non_empty(norm, "tests")
    return norm


# ---------- Type: function ----------

def _normalize_function_signature(raw: Dict[str, Any]) -> Dict[str, Any]:
    fn = raw.get("function")
    if not isinstance(fn, dict):
        raise SpecError("Missing required mapping", "function")

    name = _as_identifier(fn.get("name"), "function.name")
    args = fn.get("arguments") or fn.get("args")
    if not isinstance(args, list):
        raise SpecError("function.arguments must be a list", "function.arguments")

    norm_args: List[Dict[str, str]] = []
    for i, a in enumerate(args):
        apath = f"function.arguments[{i}]"
        if not isinstance(a, dict):
            raise SpecError("Each argument must be a mapping", apath)
        aname = _as_identifier(a.get("name"), f"{apath}.name")
        atype = _as_type(a.get("type", "any"), f"{apath}.type")
        _reject_unknown_keys(a, allowed={"name", "type"}, path=apath)
        norm_args.append({"name": aname, "type": atype})

    returns = fn.get("returns", "any")
    if returns is not None:
        returns = _as_type(returns, "function.returns")

    _reject_unknown_keys(fn, allowed={"name", "arguments", "args", "returns"}, path="function")

    return {"name": name, "args": norm_args, "returns": returns}


def _normalize_function_tests(raw: Dict[str, Any], fn: Dict[str, Any]) -> List[Dict[str, Any]]:
    tests = _require_tests_list(raw)
    arg_order = [a["name"] for a in fn["args"]]

    norm: List[Dict[str, Any]] = []
    for i, t in enumerate(tests):
        path = f"tests[{i}]"
        if not isinstance(t, dict):
            raise SpecError("Each test must be a mapping", path)

        name = _require_name(t, path)

        if "args" not in t or not isinstance(t["args"], dict):
            raise SpecError("args must be a mapping keyed by argument names", f"{path}.args")

        # Build positional args array in declared order
        mapping = t["args"]
        _check_exact_keys(mapping, expected_keys=set(arg_order), path=f"{path}.args")
        pos_args = [mapping[k] for k in arg_order]

        has_expected = "expected" in t
        has_exception = "exception" in t
        if has_expected == has_exception:
            raise SpecError("Provide exactly one of 'expected' or 'exception'", path)

        entry: Dict[str, Any] = {"name": name, "args": pos_args}
        if has_expected:
            entry["expected"] = t["expected"]
        else:
            entry["exception"] = _normalize_exception(t["exception"], f"{path}.exception")

        _reject_unknown_keys(t, allowed={"name", "args", "expected", "exception"}, path=path)
        norm.append(entry)

    _require_non_empty(norm, "tests")
    return norm


# ---------- Type: oop ----------

def _normalize_class_signature(raw: Dict[str, Any]) -> Dict[str, Any]:
    c = raw.get("class")
    if not isinstance(c, dict):
        raise SpecError("Missing required mapping", "class")

    name = _as_identifier(c.get("name"), "class.name")

    methods = c.get("methods")
    if not isinstance(methods, list) or not methods:
        raise SpecError("class.methods must be a non-empty list", "class.methods")

    norm_methods: List[Dict[str, Any]] = []
    for i, m in enumerate(methods):
        mpath = f"class.methods[{i}]"
        if not isinstance(m, dict):
            raise SpecError("Each method must be a mapping", mpath)
        mname_raw = _as_identifier(m.get("name"), f"{mpath}.name")
        mname = "__init__" if mname_raw == "init" else mname_raw

        margs = m.get("arguments") or m.get("args") or []
        if not isinstance(margs, list):
            raise SpecError("method arguments must be a list", f"{mpath}.arguments")
        norm_margs = []
        for j, a in enumerate(margs):
            apath = f"{mpath}.arguments[{j}]"
            if not isinstance(a, dict):
                raise SpecError("Each argument must be a mapping", apath)
            aname = _as_identifier(a.get("name"), f"{apath}.name")
            atype = _as_type(a.get("type", "any"), f"{apath}.type")
            _reject_unknown_keys(a, allowed={"name", "type"}, path=apath)
            norm_margs.append({"name": aname, "type": atype})

        returns = m.get("returns", "any")
        if returns is not None:
            returns = _as_type(returns, f"{mpath}.returns")

        _reject_unknown_keys(m, allowed={"name", "arguments", "args", "returns"}, path=mpath)
        norm_methods.append({"name": mname, "args": norm_margs, "returns": returns})

    _reject_unknown_keys(c, allowed={"name", "methods"}, path="class")
    return {"name": name, "methods": norm_methods}


def _normalize_oop_tests(raw: Dict[str, Any], klass: Dict[str, Any]) -> List[Dict[str, Any]]:
    tests = _require_tests_list(raw)
    declared_methods = {m["name"] for m in klass["methods"]}

    norm: List[Dict[str, Any]] = []
    for i, t in enumerate(tests):
        path = f"tests[{i}]"
        if not isinstance(t, dict):
            raise SpecError("Each test must be a mapping", path)
        name = _require_name(t, path)

        setup_raw = t.get("setup", [])
        if not isinstance(setup_raw, list):
            raise SpecError("setup must be a list", f"{path}.setup")

        steps_raw = t.get("actions") or t.get("steps")
        if not isinstance(steps_raw, list):
            raise SpecError("actions/steps must be a list", f"{path}.actions")

        # setup: only create supported
        created_vars = set()
        setup: List[Dict[str, Any]] = []
        for j, s in enumerate(setup_raw):
            spath = f"{path}.setup[{j}]"
            if not isinstance(s, dict):
                raise SpecError("Each setup entry must be a mapping", spath)
            if s.get("action") != "create":
                raise SpecError("Only 'create' is supported in setup", spath)
            cls = _as_identifier(s.get("class"), f"{spath}.class")
            var = _as_identifier(s.get("var"), f"{spath}.var")
            setup.append({"op": "create", "class": cls, "as": var})
            created_vars.add(var)
            _reject_unknown_keys(s, allowed={"action", "class", "var"}, path=spath)

        # steps: call ops
        steps: List[Dict[str, Any]] = []
        for k, a in enumerate(steps_raw):
            apath = f"{path}.actions[{k}]"
            if not isinstance(a, dict):
                raise SpecError("Each action/step must be a mapping", apath)
            if a.get("action") != "call":
                raise SpecError("Only 'call' actions are supported", apath)

            var = _as_identifier(a.get("var"), f"{apath}.var")
            if var not in created_vars:
                raise SpecError(f"Unknown variable '{var}' (not created in setup)", f"{apath}.var")

            method = _as_identifier(a.get("method"), f"{apath}.method")
            if method not in declared_methods:
                raise SpecError(f"Method '{method}' not declared in class.methods", f"{apath}.method")

            args_map = a.get("args") or {}
            if not isinstance(args_map, dict):
                raise SpecError("args must be a mapping", f"{apath}.args")

            # Normalize to positional args based on method signature
            method_sig = _get_method_sig(klass, method)
            expected_arg_names = [x["name"] for x in method_sig["args"]]
            _check_exact_keys(args_map, set(expected_arg_names), path=f"{apath}.args")
            pos_args = [args_map[n] for n in expected_arg_names]

            has_expected = "expected" in a
            has_exception = "exception" in a
            if has_expected == has_exception:
                raise SpecError("Provide exactly one of 'expected' or 'exception'", apath)

            step: Dict[str, Any] = {"op": "call", "on": var, "method": method, "args": pos_args}
            if has_expected:
                step["expected"] = a["expected"]
            else:
                step["exception"] = _normalize_exception(a["exception"], f"{apath}.exception")

            _reject_unknown_keys(a, allowed={"action", "var", "method", "args", "expected", "exception"}, path=apath)
            steps.append(step)

        _reject_unknown_keys(t, allowed={"name", "setup", "actions", "steps"}, path=path)
        norm.append({"name": name, "setup": setup, "steps": steps})

    _require_non_empty(norm, "tests")
    return norm


# ---------- Small utilities ----------

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

def _as_identifier(val: Any, path: str) -> str:
    s = _as_str(val, path)
    if not _IDENT_RE.match(s):
        raise SpecError("must be a valid identifier (letters, digits, underscore; cannot start with digit)", path)
    return s


def _as_type(val: Any, path: str) -> str:
    s = _as_str(val, path)
    # allow a small, extensible set
    allowed = {"integer", "float", "string", "bool", "any", "void"}
    if s not in allowed:
        raise SpecError(f"type must be one of {sorted(allowed)}", path)
    return s


def _as_str(val: Any, path: str) -> str:
    if not isinstance(val, str):
        raise SpecError("must be a string", path)
    return val


def _normalize_newlines(s: str) -> str:
    return s.replace("\r\n", "\n").replace("\r", "\n")


def _require_tests_list(raw: Dict[str, Any]) -> List[Any]:
    tests = raw.get("tests")
    if not isinstance(tests, list):
        raise SpecError("tests must be a list", "tests")
    return tests


def _require_non_empty(seq: List[Any], path: str) -> None:
    if not seq:
        raise SpecError("must contain at least one item", path)


def _require_name(obj: Dict[str, Any], path: str) -> str:
    if "name" not in obj:
        raise SpecError("Missing required key 'name'", f"{path}.name")
    return _as_identifier(obj["name"], f"{path}.name")


def _reject_unknown_keys(obj: Dict[str, Any], *, allowed: set[str], path: str) -> None:
    for k in obj.keys():
        if k not in allowed:
            raise SpecError(f"Unknown key '{k}'", f"{path}.{k}")


def _check_exact_keys(mapping: Dict[str, Any], expected_keys: set[str], *, path: str) -> None:
    actual = set(mapping.keys())
    missing = expected_keys - actual
    extra = actual - expected_keys
    if missing or extra:
        parts = []
        if missing:
            parts.append(f"missing: {sorted(missing)}")
        if extra:
            parts.append(f"unexpected: {sorted(extra)}")
        raise SpecError("; ".join(parts), path)


def _get_method_sig(klass: Dict[str, Any], method_name: str) -> Dict[str, Any]:
    for m in klass["methods"]:
        if m["name"] == method_name:
            return m
    # Should be unreachable due to earlier validation
    raise SpecError(f"Method '{method_name}' not found", "class.methods")


def _normalize_exception(val: Any, path: str) -> dict:
    """
    Normalize an exception field.
    - If a plain string is given, treat it as {"type": string}.
    - If a mapping, require 'type' and optional 'message'.
    """
    if isinstance(val, str):
        return {"type": val}

    if isinstance(val, dict):
        if "type" not in val:
            raise SpecError("exception mapping must include 'type'", path)
        etype = _as_str(val["type"], f"{path}.type")
        result = {"type": etype}
        if "message" in val:
            result["message"] = _as_str(val["message"], f"{path}.message")
        _reject_unknown_keys(val, allowed={"type", "message"}, path=path)
        return result

    raise SpecError("exception must be a string or mapping", path)
