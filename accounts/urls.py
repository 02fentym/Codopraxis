from django.urls import path, include, reverse_lazy
from .views import email_login_view, signup_view
from django.contrib.auth import views as auth_views
from .forms import StyledPasswordResetForm, StyledSetPasswordForm

urlpatterns = [
    path("login/",  email_login_view, name="login"),
    path("signup/", signup_view,      name="signup"), 

    # password reset (all hyphenated)
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="registration/password_reset_form.html",
            email_template_name="registration/password_reset_email.txt",
            subject_template_name="registration/password_reset_subject.txt",
            success_url=reverse_lazy("password-reset-done"),
            form_class=StyledPasswordResetForm,
        ),
        name="password-reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="registration/password_reset_done.html"
        ),
        name="password-reset-done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="registration/password_reset_confirm.html",
            success_url=reverse_lazy("password-reset-complete"),
            form_class=StyledSetPasswordForm,
        ),
        name="password-reset-confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="registration/password_reset_complete.html"
        ),
        name="password-reset-complete",
    ),

    # keep default auth urls last
    path("", include("django.contrib.auth.urls")),
]
