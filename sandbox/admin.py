# sandbox/admin.py
from django.contrib import admin
from django.db import transaction
from .models import Language, Runtime


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "file_extension", "syntax_highlighter_mode", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "slug", "file_extension", "syntax_highlighter_mode")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)


@admin.register(Runtime)
class RuntimeAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "language",
        "docker_image",
        "compile_command",
        "run_command",
        "default_entry_filename",
        "is_default",
    )
    list_filter = ("language", "is_default")
    search_fields = ("name", "slug", "docker_image", "compile_command", "run_command", "default_entry_filename")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("language__name", "name")
    list_editable = ("is_default",)

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        """
        Keep exactly one is_default per language (convenience on top of the DB constraint).
        If this runtime is marked default, unset it for all its siblings.
        """
        super().save_model(request, obj, form, change)
        if obj.is_default:
            Runtime.objects.filter(language=obj.language).exclude(pk=obj.pk).update(is_default=False)
