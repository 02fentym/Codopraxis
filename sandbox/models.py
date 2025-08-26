from django.db import models

# Create your models here.

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
    
