# codequestions/admin.py
from django.contrib import admin
from .models import CodeQuestion
from .forms import CodeQuestionForm   # <-- make sure this import exists

@admin.register(CodeQuestion)
class CodeQuestionAdmin(admin.ModelAdmin):
    form = CodeQuestionForm
    list_display = ("id", "topic", "compiled_version", "created", "updated")
    list_filter = ("topic",)
    search_fields = ("yaml_spec",)
    readonly_fields = ("created", "updated", "compiled_at", "compiled_version")
