# accounts/forms.py
from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, PasswordResetForm, SetPasswordForm
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

User = get_user_model()

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


class SignUpForm(forms.ModelForm):
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={"autocomplete": "email", "class": "input input-bordered w-full"})
    )
    password1 = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "class": "input input-bordered w-full"}),
        help_text=None,  # Django will inject help_text via template if you want
    )
    password2 = forms.CharField(
        label="Confirm password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "class": "input input-bordered w-full"}),
    )

    class Meta:
        model = User
        fields = ("email",)

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Passwords do not match.")
        # Run Django’s password validators
        if p1:
            validate_password(p1, user=None)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"].lower()
        # If you’re using a custom user with email as username, you may want:
        if hasattr(user, "username") and not user.username:
            user.username = user.email  # harmless if username field exists
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class ResendActivationForm(forms.Form):
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={"autocomplete": "email", "class": "input input-bordered w-full"})
    )