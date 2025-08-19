from django.contrib import admin, messages
from django.db import models
from django import forms
from django.utils.html import format_html
from .models import CodeQuestion, CodeTestCase
from .compiler import compile_question
from .forms import CodeQuestionForm
import json

# codequestions/admin.py

class CodeTestCaseInline(admin.TabularInline):
    model = CodeTestCase
    extra = 0
    ordering = ("order", "id")
    # REMOVE test_runner_cache from the form
    fields = ("name", "order", "is_active", "data", "created_at", "updated_at")
    # Option A: don't show it at all (simplest)
    # exclude = ("test_runner_cache",)

    # Option B: show it but read-only (safe)
    readonly_fields = ("created_at", "updated_at",)  # add "test_runner_cache" here if you want to display it

    formfield_overrides = {
        models.JSONField: {"widget": forms.Textarea(attrs={"rows": 8, "cols": 100})},
    }
    show_change_link = True



@admin.action(description="Compile compiled_spec for selected CodeQuestions")
def compile_selected(modeladmin, request, queryset):
    total = 0
    for q in queryset:
        res = compile_question(q)
        total += res.count
    messages.success(
        request,
        f"Compiled {queryset.count()} question(s). Total active cases processed: {total}."
    )


@admin.register(CodeQuestion)
class CodeQuestionAdmin(admin.ModelAdmin):
    form = CodeQuestionForm
    list_display = ("id", "test_style", "topic", "compiled_version", "created", "updated")
    list_filter = ("test_style", "topic")
    search_fields = ("prompt",)
    readonly_fields = (
        "created", "updated", "compiled_at", "compiled_version",
        "pretty_compiled_spec",
    )
    inlines = [CodeTestCaseInline]

    fieldsets = (
        (None, {
            "fields": ("prompt", "test_style", "topic"),
        }),
        ("Compilation", {
            "fields": ("compiled_version", "compiled_at", "pretty_compiled_spec", "compiled_runner_cache"),
        }),
        ("Timestamps", {
            "fields": ("created", "updated"),
        }),
    )

    @admin.display(description="Compiled Spec (pretty)")
    def pretty_compiled_spec(self, obj):
        raw = getattr(obj, "compiled_spec", None)
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
            pretty = json.dumps(data, indent=4, ensure_ascii=False)
        except Exception:
            pretty = raw if isinstance(raw, str) else str(raw)
        return format_html("<pre style='white-space:pre-wrap;margin:0'>{}</pre>", pretty)




@admin.register(CodeTestCase)
class CodeTestCaseAdmin(admin.ModelAdmin):
    list_display = ("id", "code_question", "name", "order", "is_active", "created_at", "updated_at")
    list_filter = ("is_active", "code_question__test_style")
    search_fields = ("name", "code_question__prompt")
    ordering = ("code_question", "order", "id")
    readonly_fields = ("created_at", "updated_at")
    formfield_overrides = {
        models.JSONField: {"widget": forms.Textarea(attrs={"rows": 12, "cols": 100})},
    }
