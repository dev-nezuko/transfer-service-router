from rest_framework import status, viewsets
from rest_framework.response import Response
from django.contrib.gis.geos import Point
from .coordinates import parse_coordinates
from .models import Provider, ServiceArea
from .serializers import ProviderSerializer, ServiceAreaSerializer

class ProviderViews(viewsets.ModelViewSet):
    serializer_class = ProviderSerializer
    queryset = Provider.objects.order_by("id")

class ServiceAreaViews(viewsets.ModelViewSet):
    serializer_class = ServiceAreaSerializer
    queryset = ServiceArea.objects.order_by("id")

    def search_service_area(self, request):
        lat = request.query_params.get("lat")
        lng = request.query_params.get("lng")

        try:
            lat_f, lng_f = parse_coordinates(lat, lng)
        except ValueError as error:
            return Response({'message': str(error)}, status=status.HTTP_400_BAD_REQUEST)

        pnt = Point(lng_f, lat_f, srid=4326)
        queryset = (
            ServiceArea.objects.filter(area_polygon__isnull=False)
            .filter(area_polygon__contains=pnt)
            .order_by("id")
        )
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
