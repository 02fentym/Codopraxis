# codequestions/models.py
from django.db import models


class CodeQuestion(models.Model):
    # The new schema makes test_style and function_name fields redundant.
    # The prompt field is now also part of the YAML.
    # We will store the entire YAML content in a single field.
    yaml_spec = models.TextField(
        help_text="The full problem definition in YAML format, including tests."
    )
    
    # We can still keep starter code as a separate field if we want to
    # maintain it outside the YAML, for user-facing editing.
    starter_code = models.TextField(blank=True, default="")

    timeout_seconds = models.PositiveIntegerField(
        default=5, help_text="Max seconds a student submission may run in Docker."
    )
    memory_limit_mb = models.PositiveIntegerField(
        default=128, help_text="Max RAM (in MB) Docker container may use."
    )

    topic = models.ForeignKey("base.Topic", null=True, blank=True, on_delete=models.SET_NULL)

    # These fields are still useful for caching and tracking changes
    compiled_spec = models.JSONField(
        default=dict, blank=True, help_text="Compiled spec used to generate test runners."
    )
    compiled_at = models.DateTimeField(
        null=True, blank=True, help_text="When compiled_spec was last refreshed."
    )
    compiled_version = models.PositiveIntegerField(
        default=0, help_text="Bumped whenever compiled_spec changes."
    )
    compiled_runner_cache = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Cache of rendered test runner code per language. "
            "Format: {lang: {version, generator_version, content}}"
        ),
    )

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        # We can't use test_style anymore, so we will use a more generic name
        return f"CodeQuestion {self.id}"
