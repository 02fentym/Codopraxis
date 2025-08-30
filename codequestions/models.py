from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import hashlib
from sandbox.models import Runtime
from .constants import DEFAULT_TIMEOUT_SECONDS, DEFAULT_MEMORY_LIMIT_MB


# ---------- CodeQuestion & StructuralTest ----------

class CodeQuestion(models.Model):
    class QuestionType(models.TextChoices):
        STANDARDIO = "standardio", _("Standard I/O")
        STRUCTURAL = "structural", _("Structural")

    question_type = models.CharField(max_length=20, choices=QuestionType.choices)
    prompt = models.TextField()

    # Execution guards
    timeout_seconds = models.PositiveIntegerField(default=DEFAULT_TIMEOUT_SECONDS)
    memory_limit_mb = models.PositiveIntegerField(default=DEFAULT_MEMORY_LIMIT_MB)

    # Only for standardio questions (language-agnostic tests)
    tests_json = models.JSONField(null=True, blank=True)

    # (Topic intentionally omitted per your note; can add later)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created"]

    def clean(self):
        super().clean()

        if self.question_type == self.QuestionType.STANDARDIO:
            # Must have tests_json and it must be a list of cases or an object with test_cases
            if not self.tests_json:
                raise ValidationError({"tests_json": "Standard I/O questions require tests_json."})
            # Minimal structural validation (kept light; you can strengthen later)
            try:
                data = self.tests_json
                if isinstance(data, dict):
                    cases = data.get("test_cases", [])
                else:
                    cases = data
                if not isinstance(cases, list) or len(cases) == 0:
                    raise ValueError
            except Exception:
                raise ValidationError({"tests_json": "tests_json must include one or more test cases."})

        elif self.question_type == self.QuestionType.STRUCTURAL:
            # Must not have tests_json at all
            if self.tests_json not in (None, {}, []):
                raise ValidationError({"tests_json": "Structural questions must not define tests_json."})

    def __str__(self):
        return f"[{self.get_question_type_display()}] #{self.pk or 'new'}"


class StructuralTest(models.Model):
    code_question = models.ForeignKey(
        CodeQuestion, on_delete=models.CASCADE, related_name="structural_tests"
    )
    runtime = models.ForeignKey(
        Runtime, on_delete=models.PROTECT, related_name="structural_tests"
    )
    test_source = models.TextField()
    sha256 = models.CharField(max_length=64, editable=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["code_question", "runtime"],
                name="unique_structural_test_per_runtime",
            )
        ]

    def clean(self):
        if self.code_question and self.code_question.question_type != CodeQuestion.QuestionType.STRUCTURAL:
            raise ValidationError("StructuralTest can only be attached to a structural CodeQuestion.")
        if not self.test_source.strip():
            raise ValidationError({"test_source": "Test source cannot be empty."})

    def save(self, *args, **kwargs):
        normalized = self.test_source.replace("\r\n", "\n").encode("utf-8")
        self.sha256 = hashlib.sha256(normalized).hexdigest()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Test for Q{self.code_question_id} on {self.runtime.slug}"
