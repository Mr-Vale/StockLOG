from django.shortcuts import redirect


class AccountBoundaryMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and (
            not request.user.is_active or not request.user.property_id
        ):
            from django.contrib.auth import logout

            logout(request)
            return redirect("login")
        response = self.get_response(request)
        if not request.path.startswith("/static/"):
            response["Cache-Control"] = "no-store"
            response["Vary"] = "Cookie"
        response["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        return response
