# codequestions/forms.py
from django import forms
from .models import CodeQuestion

class CodeQuestionForm(forms.ModelForm):
    class Meta:
        model = CodeQuestion
        fields = "__all__"
        widgets = {
            "starter_code": forms.Textarea(
                attrs={"rows": 12, "cols": 100, "style": "font-family: monospace;"}
            ),
        }
