"""HTTP layer: request parsing, serialisation and pagination only.

The spatial lookup itself lives in :mod:`testapp.queries`; these views decide
what a request means and what comes back, not how the database is asked.
"""

from rest_framework import generics, status, viewsets
from rest_framework.response import Response

from .models import Provider, ServiceArea
from .queries import ServiceAreaCoverageQuery
from .serializers import (
    PointSearchQuerySerializer,
    ProviderSerializer,
    ServiceAreaSerializer,
)


class ProviderViewSet(viewsets.ModelViewSet):
    """CRUD for providers."""

    serializer_class = ProviderSerializer
    # Explicit ordering keeps the paginated list endpoint deterministic.
    queryset = Provider.objects.all().order_by("id")


class ServiceAreaViewSet(viewsets.ModelViewSet):
    """CRUD for service areas."""

    serializer_class = ServiceAreaSerializer
    # select_related collapses the provider lookup into the list query.
    queryset = ServiceArea.objects.select_related("provider").order_by("id")


class ServiceAreaSearchView(generics.ListAPIView):
    """``GET /testapp/search_service_area/?lat=&lng=``.

    Returns every service area whose polygon contains the given point, newest
    pagination rules applied. Validation failures are reported as
    ``{"message": "..."}`` with ``400`` so that a client sees one readable
    string rather than a nested error object.
    """

    serializer_class = ServiceAreaSerializer
    coverage_query = ServiceAreaCoverageQuery()

    def get(self, request, *args, **kwargs):
        params = PointSearchQuerySerializer(data=request.query_params)
        if not params.is_valid():
            return Response(
                {"message": params.error_message()},
                status=status.HTTP_400_BAD_REQUEST,
            )
        self.point = params.to_point()
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return self.coverage_query.for_point(self.point)
