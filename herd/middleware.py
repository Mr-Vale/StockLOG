import time
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from .context import properties_for
from .models import PIC


class AccountBoundaryMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.farm_context = ""
        request.context_ready = False
        if request.user.is_authenticated:
            user = request.user
            pair = request.session.get("farm_selection")
            if pair is None and user.property_id and user.pic_id:
                pair = [user.property_id, user.pic_id]
                request.session["farm_selection"] = pair
            user.property = None
            user.pic = None
            if pair:
                prop = properties_for(user).filter(pk=pair[0]).first()
                pic = (
                    PIC.objects.filter(pk=pair[1], property=prop).first()
                    if prop
                    else None
                )
                if pic:
                    user.property, user.pic = prop, pic
                    generation = request.session.setdefault(
                        "farm_generation", "initial"
                    )
                    request.farm_context = signing.Signer(
                        salt="farm-context"
                    ).sign_object([prop.pk, pic.pk, generation])
                    request.context_ready = time.time() >= request.session.get(
                        "farm_ready_at", 0
                    )
            name = request.path
            exempt = (
                name
                in {
                    "/",
                    "/login/",
                    "/logout/",
                    "/health/",
                    "/properties/add/",
                    "/pics/add/",
                    "/accounts/",
                    "/access/",
                    "/context/select/",
                    "/context/ready/",
                }
                or name.startswith("/static/")
                or name == "/recovery-worker.js"
            )
            if not exempt:
                if not user.property_id or not user.pic_id or not request.context_ready:
                    return redirect("dashboard")
                if (
                    request.method == "POST"
                    and request.POST.get("farm_context") != request.farm_context
                ):
                    raise PermissionDenied(
                        "Property or PIC changed. Reload and review this form before submitting."
                    )
        response = self.get_response(request)
        if not request.path.startswith("/static/"):
            response["Cache-Control"] = "no-store"
            response["Vary"] = "Cookie"
        response["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        return response
