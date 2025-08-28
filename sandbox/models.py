from django.db import models
from django.conf import settings


class Language(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=50, unique=True)
    file_extension = models.CharField(max_length=16)  # e.g. ".py", ".java"
    syntax_highlighter_mode = models.CharField(max_length=50)  # e.g. "python", "java"
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

class Runtime(models.Model):
    name = models.CharField(max_length=100, unique=True)            # e.g. "Python 3.10"
    slug = models.SlugField(max_length=50, unique=True)             # e.g. "python310"
    language = models.ForeignKey(Language, on_delete=models.PROTECT, related_name="runtimes")
    docker_image = models.CharField(max_length=200)                 # e.g. "python:3.10-slim"
    compile_command = models.CharField(max_length=200, blank=True)  # empty for interpreted
    run_command = models.CharField(max_length=200)                  # e.g. "python -u tests.py"
    is_default = models.BooleanField(default=False)
    default_entry_filename = models.CharField(max_length=100)       # e.g. "solution.py" / "Main.java"

    class Meta:
        ordering = ["language__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["language"],
                condition=models.Q(is_default=True),
                name="one_default_runtime_per_language",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.language.slug})"
    


class Submission(models.Model):
    class Status(models.TextChoices):
        PASSED = "passed", "Passed"
        FAILED = "failed", "Failed"
        ERROR = "error", "Error"
        TIMEOUT = "timeout", "Timeout"
        OOM = "oom", "Out of Memory"
        SANDBOX_ERROR = "sandbox_error", "Sandbox Error"
        UNKNOWN = "unknown", "Unknown"

    code_question = models.ForeignKey(
        "codequestions.CodeQuestion",
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    runtime = models.ForeignKey(
        "sandbox.Runtime",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submissions",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="code_submissions",
    )

    job_id = models.CharField(max_length=32, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices)
    summary = models.JSONField(default=dict)
    junit_xml = models.TextField(blank=True)
    stdout_tail = models.TextField(blank=True)
    stderr_tail = models.TextField(blank=True)

    timeout_seconds = models.PositiveIntegerField(default=5)
    memory_limit_mb = models.PositiveIntegerField(default=256)
    duration_s = models.FloatField(null=True, blank=True)

    student_code = models.TextField()

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return f"Submission #{self.pk} Q{self.code_question_id} {self.status}"
