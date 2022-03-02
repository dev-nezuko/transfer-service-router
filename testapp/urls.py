from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import ProviderViewSet, ServiceAreaSearchView, ServiceAreaViewSet

router = SimpleRouter()
router.register("provider", ProviderViewSet, basename="provider")
router.register("service_area", ServiceAreaViewSet, basename="service_area")

urlpatterns = [
    path("", include(router.urls)),
    path(
        "search_service_area/",
        ServiceAreaSearchView.as_view(),
        name="search_service_area",
    ),
]
