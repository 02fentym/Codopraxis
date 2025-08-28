# sandbox/admin.py
from django.contrib import admin, messages
from django.db import transaction
from django.utils.html import format_html

from .models import Language, Runtime, Submission


# ----------------------
# Language
# ----------------------
@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "file_extension", "syntax_highlighter_mode", "is_active", "runtime_count")
    list_filter = ("is_active",)
    search_fields = ("name", "slug", "file_extension", "syntax_highlighter_mode")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)

    def runtime_count(self, obj):
        return obj.runtimes.count()
    runtime_count.short_description = "Runtimes"


# ----------------------
# Runtime
# ----------------------
@admin.register(Runtime)
class RuntimeAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "language",
        "short_image",
        "is_default",
        "default_entry_filename",
    )
    list_filter = ("language", "is_default")
    search_fields = ("name", "slug", "docker_image", "default_entry_filename", "compile_command", "run_command")
    list_select_related = ("language",)
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ("language",)
    actions = ("make_default_for_language",)
    readonly_fields = ()

    def short_image(self, obj):
        img = obj.docker_image or ""
        return img if len(img) <= 30 else f"{img[:27]}…"
    short_image.short_description = "Docker image"

    @admin.action(description="Set selected runtime(s) as the default for their language")
    def make_default_for_language(self, request, queryset):
        """
        Ensures the selected runtime becomes the only default for its language.
        We handle each selected row independently (so you can fix multiple languages at once).
        """
        updated = 0
        with transaction.atomic():
            for rt in queryset.select_related("language"):
                # Clear any existing default in this language
                Runtime.objects.filter(language=rt.language, is_default=True).update(is_default=False)
                # Set selected as default
                rt.is_default = True
                rt.save(update_fields=["is_default"])
                updated += 1
        messages.success(request, f"Set {updated} runtime(s) as default for their language(s).")


# ----------------------
# Submission
# ----------------------
@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "code_question",
        "runtime",
        "user",
        "status",
        "summary_counts",
        "duration_s",
        "timeout_seconds",
        "memory_limit_mb",
        "created",
    )
    list_filter = ("status", "runtime", "runtime__language")
    search_fields = (
        "id", "job_id",
        "code_question__id",
        "runtime__name", "runtime__slug",
        "user__username", "user__email",
    )
    list_select_related = ("runtime", "runtime__language", "code_question", "user")
    readonly_fields = ("created", "updated")
    raw_id_fields = ("code_question", "user")

    fieldsets = (
        (None, {
            "fields": ("code_question", "runtime", "user", "status", "job_id", "duration_s")
        }),
        ("Limits", {
            "fields": ("timeout_seconds", "memory_limit_mb"),
        }),
        ("Summary & Outputs", {
            "fields": ("summary", "junit_xml", "stdout_tail", "stderr_tail"),
        }),
        ("Timestamps", {
            "fields": ("created", "updated"),
        }),
    )

    def summary_counts(self, obj):
        s = obj.summary or {}
        tests = s.get("tests", 0)
        fails = s.get("failures", 0)
        errs = s.get("errors", 0)
        return f"T:{tests} F:{fails} E:{errs}"
    summary_counts.short_description = "Summary"
