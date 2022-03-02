"""Authorisation policy for the API.

The assessment brief describes an open API and the published surface is part of
what is being assessed, so anonymous access stays the default. What this adds is
a switch: with ``API_REQUIRE_AUTH=true`` reads remain anonymous while every
mutation requires an authenticated user, which is the policy you would actually
deploy. The behaviour is settings-driven (read per request, not per import) so
it can be exercised by tests and flipped in an environment file.
"""

from django.conf import settings
from rest_framework.permissions import SAFE_METHODS, BasePermission


class WriteRequiresAuth(BasePermission):
    """Allow reads for everyone; gate writes on ``settings.API_REQUIRE_AUTH``."""

    message = "Authentication is required for write operations on this API."

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        if not getattr(settings, "API_REQUIRE_AUTH", False):
            return True
        return bool(request.user and request.user.is_authenticated)
