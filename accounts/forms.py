# accounts/forms.py
from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, PasswordResetForm, SetPasswordForm
from django.contrib.auth import get_user_model


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={
            "autocomplete": "email",
            "class": "input input-bordered w-full",
            "placeholder": "you@example.com",
            "autofocus": "autofocus"
        })
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={
            "autocomplete": "current-password",
            "class": "input input-bordered w-full",
            "placeholder": "••••••••",
        }),
    )
    remember_me = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={"class": "checkbox"}),
        label="Remember me",
    )


class EmailUserCreationForm(UserCreationForm):
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={
            "autocomplete": "email",
            "class": "input input-bordered w-full",
            "placeholder": "you@example.com",
            "autofocus": "autofocus"
        })
    )
    password1 = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={
            "autocomplete": "new-password",
            "class": "input input-bordered w-full",
            "placeholder": "Create a password",
        }),
        help_text="",  # hide default help text
    )
    password2 = forms.CharField(
        label="Confirm password",
        strip=False,
        widget=forms.PasswordInput(attrs={
            "autocomplete": "new-password",
            "class": "input input-bordered w-full",
            "placeholder": "Repeat your password",
        }),
        help_text="",  # hide default help text
    )


    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("email",)  # email + password1/password2 come from UserCreationForm


class StyledPasswordResetForm(PasswordResetForm):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"class": "input input-bordered w-full"})
    )


class StyledSetPasswordForm(SetPasswordForm):
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "input input-bordered w-full"})
    )
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "input input-bordered w-full"})
    )
