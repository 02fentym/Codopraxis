from django.contrib import admin
from django.utils.html import escape
from django.utils.safestring import mark_safe
import json

from .models import CodeQuestion


@admin.register(CodeQuestion)
class CodeQuestionAdmin(admin.ModelAdmin):
    """
    Admin shows a pretty-printed compiled_spec (read-only),
    plus timeout/memory (editable if present) and common audit fields (read-only).
    """

    # Columns in the changelist
    def get_list_display(self, request):
        cols = ["id", "question_type"]
        for name in ("timeout_seconds", "memory_limit_mb", "created", "updated"):
            if hasattr(self.model, name):
                cols.append(name)
        return cols

    # Read-only fields on the detail page
    def get_readonly_fields(self, request, obj=None):
        ro = ["compiled_spec_pretty"]
        for name in ("compiled_version", "compiled_at", "created", "updated"):
            if hasattr(self.model, name):
                ro.append(name)
        # NOTE: we intentionally DO NOT add timeout/memory to readonly so they remain editable
        return ro

    # Field layout on the detail page
    def get_fields(self, request, obj=None):
        fields = ["compiled_spec_pretty"]
        # Show execution limits right under the pretty spec if present
        for name in ("timeout_seconds", "memory_limit_mb"):
            if hasattr(self.model, name):
                fields.append(name)
        # Then any audit fields
        for name in ("compiled_version", "compiled_at", "created", "updated"):
            if hasattr(self.model, name):
                fields.append(name)
        return fields

    # Derived column: type from compiled_spec
    def question_type(self, obj):
        try:
            data = getattr(obj, "compiled_spec", None) or {}
            return data.get("type") or ""
        except Exception:
            return ""
    question_type.short_description = "Type"

    # Pretty JSON block
    def compiled_spec_pretty(self, obj):
        data = getattr(obj, "compiled_spec", None)
        if not data:
            return mark_safe("<em>No compiled_spec</em>")
        try:
            pretty = json.dumps(data, ensure_ascii=False, indent=2)
            return mark_safe(
                f'<pre style="white-space:pre-wrap;word-break:break-word;margin:0">'
                f"{escape(pretty)}"
                f"</pre>"
            )
        except Exception as e:
            return mark_safe(f"<em>Unable to render JSON: {escape(str(e))}</em>")
    compiled_spec_pretty.short_description = "Compiled Spec"
