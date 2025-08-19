from django import forms


class CodeSubmissionForm(forms.Form):
    code = forms.CharField(
        widget=forms.Textarea(attrs={
            "rows": 14,
            "class": "textarea textarea-bordered w-full font-mono text-sm",
            "placeholder": "# write your solution here\nprint('Hello, world!')",
        }),
        label="Your solution (solution.py)",
        required=True,
    )