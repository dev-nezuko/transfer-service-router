from django.contrib import admin

from testapp.models import Provider, ServiceArea


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "email", "phone", "language", "currency")
    search_fields = ("name", "email", "phone")


@admin.register(ServiceArea)
class ServiceAreaAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "provider", "price", "has_polygon")
    list_select_related = ("provider",)
    search_fields = ("name",)
    list_filter = ("provider",)

    @admin.display(boolean=True, description="Polygon")
    def has_polygon(self, obj):
        return obj.area_polygon is not None
