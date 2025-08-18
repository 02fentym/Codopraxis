from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required


@login_required(login_url="login")
def home(request):
    return render(request, "base/home.html")


def gate_to_home_or_login(request):
    if request.user.is_authenticated:
        return render(request, "base/home.html")  # your base app’s home
    # preserve ?next so they come back to "/"
    login_url = reverse("login")
    return redirect(f"{login_url}?next=/")
