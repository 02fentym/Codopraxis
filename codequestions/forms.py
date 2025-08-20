# codequestions/forms.py
from __future__ import annotations

import json
import yaml

from django import forms
from django.utils import timezone
from django.db import transaction

from .models import CodeQuestion
from .spec_compiler import compile_yaml_to_spec, SpecError
from .widgets import StandardIoTestsWidget, FunctionTestsWidget


class CodeQuestionForm(forms.ModelForm):
    # Editor for standardIo tests (JSON list of {name, stdin, stdout})
    tests_editor = forms.CharField(
        required=False,
        widget=StandardIoTestsWidget,
        help_text="Edit test cases for standard IO problems.",
        label="Tests Editor (standardIo)",
    )

    # Editor for function tests (JSON rows with args + expected/exception)
    function_tests_editor = forms.CharField(
        required=False,
        widget=FunctionTestsWidget,
        help_text="Edit test cases for function problems.",
        label="Tests Editor (function)",
    )

    class Meta:
        model = CodeQuestion
        fields = [
            "yaml_spec",
            "starter_code",
            "timeout_seconds",
            "memory_limit_mb",
            "topic",
        ]

    # internal caches during clean/save
    _compiled_spec_cache: dict | None = None
    _detected_type: str | None = None

    # to detect if user actually edited the editor widgets
    _initial_stdio_json: str | None = None
    _initial_function_json: str | None = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Default: both editors hidden until we detect a type
        self.fields["tests_editor"].widget = forms.HiddenInput()
        self.fields["function_tests_editor"].widget = forms.HiddenInput()

        # Try to detect type from current YAML (initial or posted)
        yaml_text = self.initial.get("yaml_spec") or self.data.get(self.add_prefix("yaml_spec"), "")
        try:
            raw = next(yaml.safe_load_all(yaml_text)) if (yaml_text and yaml_text.strip()) else None
        except Exception:
            raw = None

        # ----- standardIo -----
        if isinstance(raw, dict) and raw.get("type") == "standardIo":
            self._detected_type = "standardIo"
            tests = []

            # Prefer compiled_spec (stable) if instance exists; else seed from YAML
            if self.instance and self.instance.pk and self.instance.compiled_spec:
                tests = self.instance.compiled_spec.get("tests") or []
            elif isinstance(raw.get("tests"), list):
                for t in raw["tests"]:
                    if isinstance(t, dict):
                        tests.append({
                            "name": t.get("name", "case"),
                            "stdin": t.get("stdin", "") or "",
                            "stdout": t.get("stdout", "") or "",
                        })

            # Show ONLY the stdio editor
            self.fields["tests_editor"].widget = StandardIoTestsWidget()
            self.fields["tests_editor"].help_text = "Edit test cases for standard IO problems."
            initial_json = json.dumps(tests)
            self.initial["tests_editor"] = initial_json
            self._initial_stdio_json = initial_json

            # Keep function editor hidden & empty to avoid accidental posts
            self.initial["function_tests_editor"] = ""
            self.fields["function_tests_editor"].widget = forms.HiddenInput()

        # ----- function -----
        elif isinstance(raw, dict) and raw.get("type") == "function":
            self._detected_type = "function"
            fn = raw.get("function") or {}
            arg_names = [
                a.get("name")
                for a in (fn.get("arguments") or fn.get("args") or [])
                if isinstance(a, dict) and a.get("name")
            ]

            rows = []
            if (
                self.instance
                and self.instance.pk
                and self.instance.compiled_spec
                and self.instance.compiled_spec.get("type") == "function"
            ):
                # Re-map positional args back to a mapping using compiled arg order
                order = [a["name"] for a in (self.instance.compiled_spec.get("function") or {}).get("args", [])]
                for t in self.instance.compiled_spec.get("tests", []):
                    mapping = dict(zip(order, t.get("args", [])))
                    if "expected" in t:
                        rows.append({
                            "name": t.get("name", "case"),
                            "args": mapping,
                            "outcome": "expected",
                            "expected": t["expected"],
                        })
                    else:
                        exc = t.get("exception", {})
                        if isinstance(exc, dict):
                            etype = exc.get("type") or "Exception"
                            emsg = exc.get("message") or ""
                        else:
                            etype = str(exc) or "Exception"
                            emsg = ""
                        rows.append({
                            "name": t.get("name", "case"),
                            "args": mapping,
                            "outcome": "exception",
                            "exception_type": etype,
                            "exception_message": emsg,
                        })
            else:
                # Seed directly from YAML (args should be a mapping in YAML)
                for t in (raw.get("tests") or []):
                    if not isinstance(t, dict):
                        continue
                    base = {"name": t.get("name", "case"), "args": (t.get("args") or {})}
                    if "expected" in t:
                        base.update({"outcome": "expected", "expected": t.get("expected")})
                    elif "exception" in t:
                        exc = t.get("exception")
                        if isinstance(exc, str):
                            base.update({"outcome": "exception", "exception_type": exc, "exception_message": ""})
                        elif isinstance(exc, dict):
                            base.update({
                                "outcome": "exception",
                                "exception_type": exc.get("type") or "Exception",
                                "exception_message": exc.get("message") or "",
                            })
                    rows.append(base)

            # Show ONLY the function editor
            self.fields["function_tests_editor"].widget = FunctionTestsWidget(attrs={
                "data-arg-names": json.dumps(arg_names)
            })
            self.fields["function_tests_editor"].help_text = "Edit test cases for function problems."
            initial_json = json.dumps(rows)
            self.initial["function_tests_editor"] = initial_json
            self._initial_function_json = initial_json

            # Keep stdio editor hidden & empty to avoid accidental posts
            self.initial["tests_editor"] = ""
            self.fields["tests_editor"].widget = forms.HiddenInput()

        else:
            # Unknown/invalid YAML: keep both editors hidden
            self.initial["tests_editor"] = ""
            self.initial["function_tests_editor"] = ""

    # ------------------ validation/compilation ------------------

    def clean_yaml_spec(self):
        text = self.cleaned_data.get("yaml_spec", "")

        # ----- standardIo -----
        if self._is_standard_io_by_text(text):
            editor_json = self.data.get(self.add_prefix("tests_editor"), "")
            editor_changed = bool(editor_json) and editor_json != (self._initial_stdio_json or "")
            if editor_json and editor_changed:
                try:
                    rows = json.loads(editor_json)
                    if self._stdio_rows_meaningful(rows):
                        raw = next(yaml.safe_load_all(text))
                        new_tests = [{
                            "name": (r.get("name") or "case"),
                            "stdin": r.get("stdin") or "",
                            "stdout": r.get("stdout") or "",
                        } for r in rows]
                        raw["tests"] = new_tests
                        text = yaml.safe_dump(raw, sort_keys=False, allow_unicode=True)
                except Exception as e:
                    raise forms.ValidationError(f"Tests editor error: {e}")

        # ----- function -----
        elif self._is_function_by_text(text):
            editor_json = self.data.get(self.add_prefix("function_tests_editor"), "")
            editor_changed = bool(editor_json) and editor_json != (self._initial_function_json or "")
            if editor_json and editor_changed:
                try:
                    rows = json.loads(editor_json) or []
                    if self._function_rows_meaningful(rows):
                        raw = next(yaml.safe_load_all(text))
                        fn = raw.get("function") or {}
                        arg_names = [
                            a.get("name")
                            for a in (fn.get("arguments") or fn.get("args") or [])
                            if isinstance(a, dict) and a.get("name")
                        ]

                        def parse_scalar(val):
                            # Let users type numbers/bools/etc. and get them parsed naturally
                            if isinstance(val, str):
                                v = val.strip()
                                if v == "":
                                    return ""
                                try:
                                    return yaml.safe_load(v)
                                except Exception:
                                    return val
                            return val

                        new_tests = []
                        for r in rows:
                            arg_map = {an: parse_scalar((r.get("args") or {}).get(an, "")) for an in arg_names}
                            entry = {"name": r.get("name") or "case", "args": arg_map}
                            outcome = (r.get("outcome") or "expected").strip().lower()
                            if outcome == "expected":
                                exp = r.get("expected", "")
                                # Only include 'expected' if not blank; otherwise omit to avoid clobbering YAML
                                if not (isinstance(exp, str) and exp.strip() == ""):
                                    entry["expected"] = parse_scalar(exp)
                            else:
                                etype = (r.get("exception_type") or "Exception").strip() or "Exception"
                                emsg = r.get("exception_message", "")
                                entry["exception"] = {"type": etype}
                                if emsg:
                                    entry["exception"]["message"] = emsg
                            new_tests.append(entry)

                        raw["tests"] = new_tests
                        text = yaml.safe_dump(raw, sort_keys=False, allow_unicode=True)
                except Exception as e:
                    raise forms.ValidationError(f"Function tests editor error: {e}")

        # Compile (with possibly updated YAML)
        try:
            compiled = compile_yaml_to_spec(text)
        except SpecError as e:
            raise forms.ValidationError(str(e))

        self._compiled_spec_cache = compiled
        return text

    @transaction.atomic
    def save(self, commit=True):
        inst: CodeQuestion = super().save(commit=False)

        # Update compiled_* fields if we compiled during clean()
        if self._compiled_spec_cache is not None:
            new_compiled = self._compiled_spec_cache
            old_compiled = inst.compiled_spec or {}
            if new_compiled != old_compiled:
                inst.compiled_spec = new_compiled
                inst.compiled_version = (inst.compiled_version or 0) + 1
                inst.compiled_at = timezone.now()

        if commit:
            inst.save()
        return inst

    # ------------------ helpers ------------------

    @staticmethod
    def _is_standard_io_by_text(text: str) -> bool:
        try:
            raw = next(yaml.safe_load_all(text))  # typo guard handled below
            return isinstance(raw, dict) and raw.get("type") == "standardIo"
        except Exception:
            try:
                raw = next(yaml.safe_load_all(text))
                return isinstance(raw, dict) and raw.get("type") == "standardIo"
            except Exception:
                return False

    @staticmethod
    def _is_function_by_text(text: str) -> bool:
        try:
            raw = next(yaml.safe_load_all(text))
            return isinstance(raw, dict) and raw.get("type") == "function"
        except Exception:
            return False

    @staticmethod
    def _stdio_rows_meaningful(rows: list) -> bool:
        """
        Returns True if any stdio row has a non-empty stdin or stdout, or a non-default name.
        Prevents clobbering YAML with empty default UI rows.
        """
        for r in rows or []:
            if not isinstance(r, dict):
                continue
            if (str(r.get("stdin", "")).strip() != "") or (str(r.get("stdout", "")).strip() != ""):
                return True
            # also treat a custom name as meaningful
            if (r.get("name") or "").strip() not in {"", "case", "case1", "baseCase"}:
                return True
        return False

    @staticmethod
    def _function_rows_meaningful(rows: list) -> bool:
        """
        Returns True if any function row has any arg filled, or expected set, or exception chosen.
        Prevents accidental overwrite when the editor posts default/empty rows.
        """
        for r in rows or []:
            if not isinstance(r, dict):
                continue
            # any arg filled?
            args = r.get("args") or {}
            for v in args.values():
                if str(v).strip() != "":
                    return True
            # expected filled?
            exp = r.get("expected", None)
            if exp is not None and str(exp).strip() != "":
                return True
            # exception chosen?
            if (r.get("outcome") or "").lower() == "exception":
                et = (r.get("exception_type") or "").strip()
                em = (r.get("exception_message") or "").strip()
                if et or em:
                    return True
        return False
