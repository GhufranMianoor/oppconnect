from django.contrib.auth import login, logout
from django.shortcuts import redirect, render

from .forms import SignUpForm


def signup(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("core:onboard_team")
    else:
        form = SignUpForm()
    return render(request, "accounts/signup.html", {"form": form})


def logout_view(request):
    """
    Plain function-based logout that works on a simple GET link.
    Django's built-in LogoutView requires POST, which can be tripped up by
    SECURE_SSL_REDIRECT converting a POST into a GET on some proxy setups
    (301 redirects turn POST into GET in the browser). A GET-based logout
    sidesteps that class of bug entirely - logging a user out has no
    destructive side effect worth CSRF-protecting against.
    """
    logout(request)
    return redirect("accounts:login")