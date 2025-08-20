# codequestions/forms.py
from __future__ import annotations

from django import forms
from django.utils import timezone
from django.db import transaction

from .models import CodeQuestion
from .spec_compiler import compile_yaml_to_spec, SpecError


class CodeQuestionForm(forms.ModelForm):
    """
    Admin form that:
      - Compiles yaml_spec → compiled_spec
      - Bumps compiled_version ONLY if the compiled_spec actually changed
      - Updates compiled_at when recompiled
      - Leaves compiled_runner_cache untouched (another action will manage it)
    """
    class Meta:
        model = CodeQuestion
        fields = [
            "yaml_spec",
            "starter_code",
            "timeout_seconds",
            "memory_limit_mb",
            "topic",
        ]

    # We'll stash the compiled dict between clean() and save()
    _compiled_spec_cache: dict | None = None

    def clean_yaml_spec(self):
        text = self.cleaned_data.get("yaml_spec", "")
        try:
            compiled = compile_yaml_to_spec(text)
        except SpecError as e:
            # raise as a field error so it shows up under the YAML box
            raise forms.ValidationError(str(e))
        self._compiled_spec_cache = compiled
        return text

    @transaction.atomic
    def save(self, commit=True):
        inst: CodeQuestion = super().save(commit=False)

        # If YAML compiled successfully in clean(), update compiled_* fields
        if self._compiled_spec_cache is not None:
            new_compiled = self._compiled_spec_cache
            old_compiled = inst.compiled_spec or {}

            if new_compiled != old_compiled:
                inst.compiled_spec = new_compiled
                inst.compiled_version = (inst.compiled_version or 0) + 1
                inst.compiled_at = timezone.now()
            else:
                # keep timestamps/version if content didn't change
                pass

        if commit:
            inst.save()
        return inst
