# codequestions/admin.py
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet

from .models import CodeQuestion, StandardIOQuestion, FunctionOOPQuestion


# ---------- Inlines ----------

class StandardIOInline(admin.StackedInline):
    model = StandardIOQuestion
    extra = 0
    max_num = 1
    can_delete = True
    verbose_name_plural = "Standard I/O authoring"
    fields = ("tests_json",)  # starter_code removed


class FunctionOOPInlineFormSet(BaseInlineFormSet):
    """
    Extra safety: if parent is standard_io, block rows here at the formset level.
    (Model.clean also enforces this, but this gives earlier admin feedback.)
    """
    def clean(self):
        super().clean()
        parent = getattr(self, "instance", None)
        if not parent or not parent.pk:
            return
        if parent.question_type == CodeQuestion.QuestionType.STANDARD_IO and any(
            form not in self.deleted_forms and not form.cleaned_data.get("DELETE", False)
            for form in self.forms if hasattr(form, "cleaned_data")
        ):
            raise ValidationError(
                "Function/OOP language specs are not allowed for a Standard I/O question."
            )


class FunctionOOPInline(admin.TabularInline):
    model = FunctionOOPQuestion
    formset = FunctionOOPInlineFormSet
    extra = 1
    verbose_name_plural = "Function/OOP language specs"
    fields = ("language", "test_framework", "entrypoint_hint", "starter_code")
    show_change_link = True


# ---------- Admins ----------

@admin.register(CodeQuestion)
class CodeQuestionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "question_type",
        "topic",
        "short_prompt",
        "timeout_seconds",
        "memory_limit_mb",
        "is_active",
        "created",
        "updated",
    )
    list_filter = ("question_type", "topic", "is_active")
    search_fields = ("prompt",)
    readonly_fields = ("created", "updated")
    fieldsets = (
        (None, {
            "fields": (
                "question_type",
                "prompt",
                "topic",
            )
        }),
        ("Limits", {
            "fields": ("timeout_seconds", "memory_limit_mb"),
        }),
        ("Flags", {
            "fields": ("is_active",),
        }),
        ("Timestamps", {
            "fields": ("created", "updated"),
        }),
    )

    def short_prompt(self, obj):
        return (obj.prompt or "")[:60]
    short_prompt.short_description = "Prompt"

    def get_inline_instances(self, request, obj=None):
        """
        - On add (obj is None): no inlines yet (author picks type, saves once).
        - On edit: show only the inlines that match the chosen question_type.
        """
        if obj is None:
            return []
        if obj.question_type == CodeQuestion.QuestionType.STANDARD_IO:
            return [StandardIOInline(self.model, self.admin_site)]
        else:
            # function or oop
            return [FunctionOOPInline(self.model, self.admin_site)]


@admin.register(StandardIOQuestion)
class StandardIOQuestionAdmin(admin.ModelAdmin):
    """
    Optional direct admin for power users.
    Usually edited through the CodeQuestion inline.
    """
    list_display = ("code_question",)
    search_fields = ("code_question__prompt",)


@admin.register(FunctionOOPQuestion)
class FunctionOOPQuestionAdmin(admin.ModelAdmin):
    """
    Optional direct admin for power users or when opening from the inline's 'change' link.
    """
    list_display = ("code_question", "language", "test_framework", "entrypoint_hint")
    list_filter = ("language", "test_framework")
    search_fields = ("code_question__prompt", "entrypoint_hint")
    fieldsets = (
        (None, {
            "fields": ("code_question", "language", "test_framework")
        }),
        ("Authoring", {
            "fields": ("entrypoint_hint", "starter_code", "test_code", "runner_meta")
        }),
    )
