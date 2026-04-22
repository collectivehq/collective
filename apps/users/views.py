from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from apps.core.utils import get_user
from apps.users.forms import ProfileForm


@login_required
def profile(request: HttpRequest) -> HttpResponse:
    user = get_user(request)
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            return redirect("users:profile")
    else:
        form = ProfileForm(instance=user)
    return render(request, "users/profile.html", {"form": form})
