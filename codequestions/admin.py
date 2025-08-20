# codequestions/admin.py
import json
from django.contrib import admin
from django.utils.safestring import mark_safe

from .models import CodeQuestion
from .forms import CodeQuestionForm


@admin.register(CodeQuestion)
class CodeQuestionAdmin(admin.ModelAdmin):
    form = CodeQuestionForm
    list_display = ("id", "topic", "compiled_version", "created", "updated")
    list_filter = ("topic",)
    search_fields = ("yaml_spec",)

    readonly_fields = (
        "compiled_at",
        "compiled_version",
        "pretty_compiled_spec",
        "compiled_tests_preview",
        "created",
        "updated",
    )

    fieldsets = (
        ("Problem Definition", {
            "fields": (
                "yaml_spec",
                "tests_editor",          # <— new editable UI for standardIo
                "function_tests_editor", # <— new editable UI for function
                "pretty_compiled_spec",
                "starter_code",
            )
        }),
        ("Metadata", {
            "fields": ("topic", "timeout_seconds", "memory_limit_mb")
        }),
        ("Compilation", {
            "fields": ("compiled_version", "compiled_at")
        }),
        ("Tests (Preview)", {
            "fields": ("compiled_tests_preview",)
        }),
        ("Timestamps", {
            "fields": ("created", "updated")
        }),
    )

    # -------- Pretty printers (unchanged) --------
    def pretty_compiled_spec(self, obj):
        if not obj.compiled_spec:
            return "(empty)"
        try:
            formatted = json.dumps(obj.compiled_spec, indent=2, ensure_ascii=False)
            return mark_safe(
                "<pre style='white-space: pre-wrap; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;'>"
                f"{formatted}</pre>"
            )
        except Exception as e:
            return f"(error formatting JSON: {e})"
    pretty_compiled_spec.short_description = "Compiled Spec"

    def compiled_tests_preview(self, obj):
        cs = obj.compiled_spec or {}
        tests = cs.get("tests") or []
        if not tests:
            return "(no tests)"

        t = cs.get("type")
        lines = []
        for i, test in enumerate(tests, start=1):
            name = test.get("name", f"test{i}")
            if t == "standardIo":
                def trunc(s, n=80):
                    s = str(s).replace("\n", "\\n")
                    return (s[:n] + "…") if len(s) > n else s
                lines.append(f"• {name}: stdin='{trunc(test.get('stdin',''))}' → stdout='{trunc(test.get('stdout',''))}'")
            elif t == "function":
                args = test.get("args", [])
                if "expected" in test:
                    lines.append(f"• {name}: {args} ⇒ expected {test['expected']}")
                else:
                    exc = test.get("exception", {})
                    etype = exc.get("type", str(exc)) if isinstance(exc, dict) else str(exc)
                    lines.append(f"• {name}: {args} ⇒ raises {etype}")
            elif t == "oop":
                setup_vars = [s.get("as") for s in test.get("setup", []) if s.get("op") == "create"]
                step_summaries = []
                for step in test.get("steps", []):
                    on, method = step.get("on"), step.get("method")
                    if "expected" in step:
                        step_summaries.append(f"{on}.{method}(…) ⇒ {step['expected']}")
                    elif "exception" in step:
                        exc = step["exception"]
                        etype = exc.get("type", str(exc)) if isinstance(exc, dict) else str(exc)
                        step_summaries.append(f"{on}.{method}(…) ⇒ raises {etype}")
                    else:
                        step_summaries.append(f"{on}.{method}(…)")
                setup_str = f"setup vars: {', '.join(v for v in setup_vars if v)}" if setup_vars else "setup: —"
                lines.append(f"• {name}: {setup_str}; steps: " + " ⟶ ".join(step_summaries))
            else:
                lines.append(f"• {name}")

        html = "<br>".join(lines)
        return mark_safe(f"<div style='line-height:1.6'>{html}</div>")
    compiled_tests_preview.short_description = "Tests (Summary)"
