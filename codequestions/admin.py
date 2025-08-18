from django.contrib import admin, messages
from django.db import models
from django import forms
from django.urls import path, reverse
from django.shortcuts import redirect
from django.utils.html import format_html

from .models import CodeQuestion, CodeTestCase
from .compiler import compile_question


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
    list_display = ("id", "test_style", "language", "topic", "compiled_version", "created", "updated")
    list_filter = ("test_style", "language", "topic")
    search_fields = ("prompt",)
    readonly_fields = ("created", "updated", "compiled_at", "compiled_version", "compile_actions")
    actions = [compile_selected]
    inlines = [CodeTestCaseInline]

    # --- Add a custom URL for the button ---
    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<int:object_id>/compile/",
                self.admin_site.admin_view(self.compile_single),
                name="codequestions_codequestion_compile",
            ),
        ]
        return custom + urls

    # --- The view that compiles a single question ---
    def compile_single(self, request, object_id: int):
        q = self.get_object(request, object_id)
        res = compile_question(q)
        messages.success(request, f"Compiled {res.count} case(s) for question #{q.pk}.")
        return redirect(reverse("admin:codequestions_codequestion_change", args=[object_id]))

    # --- A read-only field that renders the button on the change form ---
    def compile_actions(self, obj):
        if not obj or not obj.pk:
            return "-"
        url = reverse("admin:codequestions_codequestion_compile", args=[obj.pk])
        return format_html('<a class="button" href="{}">Compile now</a>', url)
    compile_actions.short_description = "Actions"


@admin.register(CodeTestCase)
class CodeTestCaseAdmin(admin.ModelAdmin):
    list_display = ("id", "code_question", "name", "order", "is_active", "created_at", "updated_at")
    list_filter = ("is_active", "code_question__test_style", "code_question__language")
    search_fields = ("name", "code_question__prompt")
    ordering = ("code_question", "order", "id")
    readonly_fields = ("created_at", "updated_at")
    formfield_overrides = {
        models.JSONField: {"widget": forms.Textarea(attrs={"rows": 12, "cols": 100})},
    }
