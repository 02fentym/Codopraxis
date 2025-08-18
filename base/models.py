from django.db import models


class Language(models.Model):
    """
    Programming language that questions can be written in (e.g., Python, Java).
    """
    slug = models.SlugField(max_length=50, unique=True)  # e.g. "python", "java"
    name = models.CharField(max_length=100, unique=True)  # e.g. "Python", "Java"

    def __str__(self):
        return self.name


class Course(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.title


class Unit(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="units")
    order = models.PositiveIntegerField()
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["course", "order"]

    def __str__(self):
        return f"{self.course.title} - {self.title}"


class Topic(models.Model):
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name="topics")
    order = models.PositiveIntegerField()
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["unit", "order"]

    def __str__(self):
        return f"{self.unit.title} - {self.title}"

