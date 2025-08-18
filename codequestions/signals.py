# codequestions/signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import CodeQuestion, CodeTestCase
from .compiler import compile_question

COMPILED_FIELDS = {"compiled_spec", "compiled_at", "compiled_version"}

@receiver(post_save, sender=CodeQuestion)
def compile_on_question_save(sender, instance: CodeQuestion, created, **kwargs):
    # Avoid infinite loop: if we just updated compiled_* fields, skip
    update_fields = kwargs.get("update_fields")
    if update_fields and set(update_fields).issubset(COMPILED_FIELDS):
        return
    # Compile on create or when non-compiled fields change
    compile_question(instance)

@receiver(post_save, sender=CodeTestCase)
def compile_on_case_save(sender, instance: CodeTestCase, **kwargs):
    compile_question(instance.code_question)

@receiver(post_delete, sender=CodeTestCase)
def compile_on_case_delete(sender, instance: CodeTestCase, **kwargs):
    compile_question(instance.code_question)
