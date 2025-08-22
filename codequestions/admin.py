# codequestions/admin.py
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.forms import ModelForm, HiddenInput, BaseInlineFormSet
from django.utils.translation import gettext_lazy as _

from .models import CodeQuestion, StructuralTest


# ---------- Forms ----------

class CodeQuestionForm(ModelForm):
    class Meta:
        model = CodeQuestion
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        qt = self.instance.question_type if self.instance and self.instance.pk else self.data.get("question_type")
        if qt == CodeQuestion.QuestionType.STRUCTURAL:
            if "tests_json" in self.fields:
                self.fields["tests_json"].required = False
                self.fields["tests_json"].widget = HiddenInput()
        else:
            if "tests_json" in self.fields:
                self.fields["tests_json"].help_text = _(
                    "Provide test cases (list or object with test_cases). Required for Standard I/O."
                )

    def clean(self):
        cleaned = super().clean()
        try:
            self.instance.question_type = cleaned.get("question_type") or self.instance.question_type
            self.instance.tests_json = cleaned.get("tests_json")
            self.instance.clean()
        except ValidationError as e:
            raise e
        return cleaned


class StructuralTestInlineFormSet(BaseInlineFormSet):
    """
    Validation:
    - Only allowed when parent is structural
    - No duplicate runtimes
    - At least one inline when editing a structural question
    """
    def clean(self):
        super().clean()
        parent = getattr(self, "instance", None)
        if not parent or not parent.pk:
            return

        if parent.question_type != CodeQuestion.QuestionType.STRUCTURAL:
            raise ValidationError(_("Structural tests are only allowed on structural questions."))

        seen = set()
        kept = 0
        for form in self.forms:
            if form.cleaned_data.get("DELETE"):
                continue

            runtime = form.cleaned_data.get("runtime")
            test_source = (form.cleaned_data.get("test_source") or "").strip()

            if not runtime:
                raise ValidationError(_("Each structural test must select a runtime."))
            if not test_source:
                raise ValidationError(_("Each structural test must include non-empty test source."))

            if runtime.pk in seen:
                raise ValidationError(_("Duplicate runtime detected. Each runtime may appear only once."))
            seen.add(runtime.pk)
            kept += 1

        if kept == 0:
            raise ValidationError(_("Provide at least one structural test."))


# ---------- Inlines ----------

class StructuralTestInline(admin.StackedInline):
    model = StructuralTest
    formset = StructuralTestInlineFormSet
    extra = 0
    min_num = 0
    fields = ("runtime", "test_source", "sha256")
    readonly_fields = ("sha256",)
    ordering = ("runtime__name",)
    verbose_name_plural = "Per‑runtime structural tests"


# ---------- Admin ----------

@admin.register(CodeQuestion)
class CodeQuestionAdmin(admin.ModelAdmin):
    form = CodeQuestionForm

    list_display = ("id", "question_type", "timeout_seconds", "memory_limit_mb", "created", "updated")
    list_filter = ("question_type", "created")
    search_fields = ("prompt",)
    readonly_fields = ("created", "updated")

    fieldsets = (
        (None, {"fields": ("question_type", "prompt")}),
        ("Execution limits", {"fields": ("timeout_seconds", "memory_limit_mb")}),
        ("Standard I/O tests", {"fields": ("tests_json",), "description": "Only used for Standard I/O questions."}),
        ("Timestamps", {"fields": ("created", "updated")}),
    )

    def get_inline_instances(self, request, obj=None):
        if obj and obj.question_type == CodeQuestion.QuestionType.STRUCTURAL:
            return [StructuralTestInline(self.model, self.admin_site)]
        return []

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.question_type == CodeQuestion.QuestionType.STRUCTURAL and obj.structural_tests.count() == 0:
            messages.info(request, "Structural question saved. Add at least one per‑runtime test below.")
