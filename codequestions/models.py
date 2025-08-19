from django.db import models


class CodeQuestion(models.Model):
    TEST_STYLE_CHOICES = [
        ("script", "Script"),
        ("function", "Function"),
        ("oop", "Object-Oriented"),
    ]

    prompt = models.TextField()
    language = models.ForeignKey("base.Language", on_delete=models.CASCADE)
    test_style = models.CharField(max_length=20, choices=TEST_STYLE_CHOICES)
    starter_code = models.TextField(blank=True, default="")

    timeout_seconds = models.PositiveIntegerField(default=5, help_text="Max seconds a student submission may run in Docker.")
    memory_limit_mb = models.PositiveIntegerField(default=128, help_text="Max RAM (in MB) Docker container may use.")

    topic = models.ForeignKey("base.Topic", null=True, blank=True, on_delete=models.SET_NULL)

    compiled_spec = models.JSONField(default=dict, blank=True, help_text="Compiled spec used to generate test runners.")
    compiled_at = models.DateTimeField(null=True, blank=True, help_text="When compiled_spec was last refreshed.")
    compiled_version = models.PositiveIntegerField(default=0, help_text="Bumped whenever compiled_spec changes.")
    compiled_runner_cache = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Cache of rendered test runner code per language. "
            "Format: {lang: {version, generator_version, content}}"
        ),
    )

    # only used when test_style == "function"
    function_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Name of the function to call for function-style questions (e.g., 'add')",
    )

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"CodeQuestion {self.id} ({self.test_style})"


class CodeTestCase(models.Model):
    """
    One row per test case. `data` holds a single normalized test case dict.
    Examples:
      script:   {"input": "3\\n5\\n", "output": "8\\n"}
      function: {"args": [4, 5], "output": "", "expected": 9}
      oop:      {"setup": [...], "calls": [...], "expected": {...}, "output": ""}
    """
    code_question = models.ForeignKey("CodeQuestion", on_delete=models.CASCADE, related_name="test_cases",)

    name = models.CharField(max_length=120, blank=True, help_text="Optional label (e.g., 'adds two numbers').")
    order = models.PositiveIntegerField(default=0, help_text="Display/execution order among this question’s cases.")
    is_active = models.BooleanField(default=True, help_text="Exclude a case without deleting it.")

    data = models.JSONField(help_text="Single test case payload (from YAML → JSON).")

    test_runner_cache = models.JSONField(default=dict, help_text="Generated test code by language (e.g., Python unittest, Java JUnit).")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"TestCase {self.name or self.pk} for CodeQuestion {self.code_question_id}"
