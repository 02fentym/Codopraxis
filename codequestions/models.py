# codequestions/models.py
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone

from base.models import Topic, Language


class CodeQuestion(models.Model):
    class QuestionType(models.TextChoices):
        STANDARD_IO = "standard_io", "Standard I/O"
        FUNCTION = "function", "Function"
        OOP = "oop", "OOP"

    question_type = models.CharField(
        max_length=20,
        choices=QuestionType.choices,
    )
    prompt = models.TextField()
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name="code_questions")

    timeout_seconds = models.PositiveIntegerField(default=5)
    memory_limit_mb = models.PositiveIntegerField(default=128)

    # Optional authoring conveniences; keep if useful now or later.
    is_active = models.BooleanField(default=True)

    created = models.DateTimeField(default=timezone.now, editable=False)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"Q{self.pk or ''} [{self.get_question_type_display()}] — {self.topic}: {self.prompt[:60]}"

    # Soft validation hook in case you later add cross-model checks here.
    def clean(self):
        super().clean()
        if self.timeout_seconds == 0:
            raise ValidationError({"timeout_seconds": "Timeout must be > 0."})
        if self.memory_limit_mb == 0:
            raise ValidationError({"memory_limit_mb": "Memory limit must be > 0."})

    @property
    def is_standard_io(self) -> bool:
        return self.question_type == self.QuestionType.STANDARD_IO

    @property
    def is_function(self) -> bool:
        return self.question_type == self.QuestionType.FUNCTION

    @property
    def is_oop(self) -> bool:
        return self.question_type == self.QuestionType.OOP


class StandardIOQuestion(models.Model):
    """
    Language-agnostic authoring for Standard I/O questions.
    """
    code_question = models.OneToOneField(
        CodeQuestion,
        on_delete=models.CASCADE,
        related_name="standard_io",
    )
    # Teacher-authored test spec. Keep structure stable; your sandbox interprets it.
    tests_json = models.JSONField(help_text="Author-provided test cases JSON (stdin/stdout pairs).")
    # Optional, language-agnostic sample scaffolds (kept out of the core).
    starter_code = models.TextField(blank=True)

    class Meta:
        verbose_name = "Standard I/O Question"
        verbose_name_plural = "Standard I/O Questions"

    def __str__(self):
        return f"Standard I/O for Q{self.code_question_id}"

    def clean(self):
        super().clean()
        if not self.code_question:
            return

        # Must be attached only to a STANDARD_IO CodeQuestion
        if not self.code_question.is_standard_io:
            raise ValidationError(
                "StandardIOQuestion can only be attached to a CodeQuestion with question_type='standard_io'."
            )

        # Must not coexist with FunctionOOPQuestion rows
        exists_other = self.code_question.function_oop_questions.exists()
        if exists_other:
            raise ValidationError(
                "This CodeQuestion already has Function/OOP language specs. "
                "A StandardIOQuestion cannot coexist with Function/OOP specs."
            )


class FunctionOOPQuestion(models.Model):
    """
    Per-language authoring for Function and OOP questions.
    One CodeQuestion may have multiple languages (Python, Java, etc.).
    """
    class TestFramework(models.TextChoices):
        UNITTEST = "unittest", "unittest"
        PYTEST = "pytest", "pytest"
        JUNIT = "junit", "JUnit"
        # Extend as needed (e.g., "mocha", "jest", etc.)

    code_question = models.ForeignKey(
        CodeQuestion,
        on_delete=models.CASCADE,
        related_name="function_oop_questions",
    )
    language = models.ForeignKey(
        Language,
        on_delete=models.CASCADE,
        related_name="function_oop_questions",
    )
    test_framework = models.CharField(
        max_length=20,
        choices=TestFramework.choices,
        help_text="e.g., unittest/pytest for Python; JUnit for Java.",
    )
    test_code = models.TextField(
        help_text="Author-written test harness in the chosen language/framework."
    )

    # Helpful extras for authoring clarity
    starter_code = models.TextField(blank=True)
    entrypoint_hint = models.CharField(
        max_length=200,
        blank=True,
        help_text="Expected function/class name or entry point description.",
    )
    runner_meta = models.JSONField(
        blank=True,
        null=True,
        help_text="Optional execution hints for the sandbox (file layout, args, env).",
    )

    class Meta:
        verbose_name = "Function/OOP Language Spec"
        verbose_name_plural = "Function/OOP Language Specs"
        constraints = [
            # Prevent duplicate language rows for the same question
            models.UniqueConstraint(
                fields=["code_question", "language"],
                name="uq_codequestion_language_once",
            ),
        ]

    def __str__(self):
        qt = self.code_question.get_question_type_display() if self.code_question_id else "N/A"
        return f"{qt} ({self.language.name}) for Q{self.code_question_id}"

    def clean(self):
        super().clean()
        if not self.code_question_id:
            return

        # Only valid if parent question is FUNCTION or OOP
        if not (self.code_question.is_function or self.code_question.is_oop):
            raise ValidationError(
                "FunctionOOPQuestion can only be attached to a CodeQuestion with "
                "question_type in {'function', 'oop'}."
            )

        # Must not coexist with StandardIOQuestion
        if hasattr(self.code_question, "standard_io"):
            raise ValidationError(
                "This CodeQuestion already has a StandardIOQuestion. "
                "You cannot add Function/OOP language specs to a Standard I/O question."
            )
