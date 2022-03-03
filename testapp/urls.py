from django.urls import path, include
from rest_framework.routers import SimpleRouter
from .views import ProviderViews, ServiceAreaViews


router = SimpleRouter()
router.register("provider", ProviderViews, basename="provider")
router.register("service_area", ServiceAreaViews, basename="service_area")

urlpatterns = [
    path("", include(router.urls)),
    path("search_service_area/", ServiceAreaViews.as_view({"get": "search_service_area"}), name="search_service_area")
]
