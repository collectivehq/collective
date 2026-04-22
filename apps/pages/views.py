from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render


def landing(request: HttpRequest) -> HttpResponse:
    """Show the marketing landing page to guests; redirect members to their spaces."""
    if request.user.is_authenticated:
        return redirect("spaces:list")
    return render(request, "pages/landing.html")
