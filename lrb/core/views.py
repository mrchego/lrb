from django.http import JsonResponse


def forbidden(request, exception=None):
    """403 for the API site: no template, so it cannot crash on a missing URL name."""
    return JsonResponse({"errors": [{"message": "Forbidden."}]}, status=403)


def not_found(request, exception=None):
    """404 for the API site (also used when the Host matches no company)."""
    return JsonResponse({"errors": [{"message": "Not found."}]}, status=404)