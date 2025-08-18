from django.conf import settings
from django.contrib.auth import login
from django.shortcuts import render, redirect
from django.urls import reverse
from .forms import EmailAuthenticationForm
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.contrib.auth import get_user_model, login


User = get_user_model()

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


def signup(request):
    from .forms import SignUpForm  # adjust if your form is elsewhere

    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False  # ⬅️ critical: require email verify
            user.save()

            # Build activation link parts
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            domain = request.get_host()
            protocol = "https" if request.is_secure() else "http"

            # Subject & body from templates
            subject = render_to_string(
                "auth/email_activation_subject.txt",
                {"user": user}
            ).strip()
            message = render_to_string(
                "auth/email_activation_email.txt",
                {"user": user, "domain": domain, "protocol": protocol, "uid": uid, "token": token}
            )

            # Send email
            send_mail(
                subject,
                message,
                getattr(settings, "DEFAULT_FROM_EMAIL", None),
                [user.email],
                fail_silently=False,
            )

            return redirect("activation-sent")
    else:
        form = SignUpForm()

    return render(request, "registration/signup.html", {"form": form})


def activate(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except Exception:
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        if not user.is_active:
            user.is_active = True
            user.save()
        # Optional: log them in automatically after activation
        login(request, user)
        return render(request, "auth/activation_complete.html", {"user": user})
    else:
        # invalid or expired token
        return render(request, "auth/activation_invalid.html")