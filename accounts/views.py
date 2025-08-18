from django.conf import settings
from django.contrib.auth import login
from django.shortcuts import render, redirect
from django.urls import reverse
from .forms import EmailAuthenticationForm, EmailUserCreationForm

def email_login_view(request):
    if request.method == "POST":
        form = EmailAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)

            # Handle “remember me”
            remember = form.cleaned_data.get("remember_me")
            if not remember:
                request.session.set_expiry(0)  # expires on browser close
            else:
                request.session.set_expiry(getattr(settings, "SESSION_COOKIE_AGE", 60 * 60 * 24 * 30))

            # Redirect to ?next=… or LOGIN_REDIRECT_URL
            next_url = request.POST.get("next") or request.GET.get("next")
            return redirect(next_url or reverse(getattr(settings, "LOGIN_REDIRECT_URL", "home")))
    else:
        form = EmailAuthenticationForm(request)

    return render(request, "registration/login.html", {"form": form})


def signup_view(request):
    if request.method == "POST":
        form = EmailUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("home")
    else:
        form = EmailUserCreationForm()

    return render(request, "registration/signup.html", {"form": form})
