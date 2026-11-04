from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django_tenants.middleware.main import TenantMainMiddleware
from django_tenants.utils import get_public_schema_name


class TenantMiddleware(TenantMainMiddleware):
    """Host -> Domain -> Company -> search_path. Also blocks deactivated companies
    before any resolver runs."""

    def process_request(self, request):
        response = super().process_request(request)
        if response is not None:
            return response
        tenant = request.tenant
        if tenant.schema_name != get_public_schema_name() and not tenant.is_active:
            raise PermissionDenied("This company is deactivated.")
        return None


class RequireGraphQLPreflightMiddleware:
    """GraphQL is csrf_exempt and tenants are sibling subdomains. Requiring a custom
    header forces a CORS preflight, so a form POST from another tenant can't ride
    the session cookie."""

    HEADER = "Apollo-Require-Preflight"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.method == "POST"
            and request.path == "/graphql/"
            and not request.headers.get(self.HEADER)
        ):
            return JsonResponse({"errors": [{"message": "Missing required header."}]}, status=403)
        return self.get_response(request)