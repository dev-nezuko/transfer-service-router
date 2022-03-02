"""DRF serializers: the translation layer between JSON and the domain models.

Every field is declared explicitly rather than through ``fields = "__all__"``,
so the wire format is visible in the code and cannot drift when a column is
added to a model.
"""

from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from rest_framework_gis.fields import GeometryField

from .geometry import GeometryFormatError, normalise_polygon
from .models import Provider, ServiceArea, phone_regex
from .queries import WGS84_SRID, point_from_lat_lng


class ProviderSerializer(serializers.ModelSerializer):
    """A transfer provider."""

    email = serializers.EmailField(
        max_length=254,
        validators=[
            UniqueValidator(
                queryset=Provider.objects.all(),
                message=(
                    "A provider with this email already exists, "
                    "please use a different one!"
                ),
            )
        ],
    )
    phone = serializers.CharField(
        max_length=17,
        validators=[
            phone_regex,
            UniqueValidator(
                queryset=Provider.objects.all(),
                message=(
                    "A provider with this phone number already exists, "
                    "please use a different one!"
                ),
            ),
        ],
    )

    class Meta:
        model = Provider
        fields = ("id", "name", "email", "phone", "language", "currency")
        read_only_fields = ("id",)


class ServiceAreaSerializer(serializers.ModelSerializer):
    """A priced polygon belonging to a provider.

    ``provider`` is a primary key rather than a slug relation on purpose:
    ``PrimaryKeyRelatedField`` reads the foreign key column that is already on
    the row, so serialising a page of areas costs one query instead of one query
    per row.
    """

    provider = serializers.PrimaryKeyRelatedField(
        queryset=Provider.objects.all(),
        required=True,
        help_text="Id of the provider that owns this area.",
    )
    area_polygon = GeometryField(
        required=False,
        allow_null=True,
        help_text=(
            "GeoJSON Polygon in WGS 84 (SRID %d), e.g. "
            '{"type": "Polygon", "coordinates": [[[lng, lat], ...]]}.' % WGS84_SRID
        ),
    )

    class Meta:
        model = ServiceArea
        fields = ("id", "name", "price", "area_polygon", "provider")
        read_only_fields = ("id",)

    def validate_area_polygon(self, value):
        """Reject anything that is not a valid WGS 84 polygon.

        Storing a self-intersecting ring is accepted by the column type but makes
        every later ``ST_Contains`` against it undefined, so it is caught here.
        """
        if value is None:
            return value
        try:
            return normalise_polygon(value)
        except GeometryFormatError as exc:
            raise serializers.ValidationError(str(exc)) from exc


class PointSearchQuerySerializer(serializers.Serializer):
    """Validation for the ``?lat=&lng=`` query string of the search endpoint."""

    lat = serializers.FloatField(min_value=-90.0, max_value=90.0)
    lng = serializers.FloatField(min_value=-180.0, max_value=180.0)

    def to_point(self):
        return point_from_lat_lng(self.validated_data["lat"], self.validated_data["lng"])

    def error_message(self):
        """Flatten ``errors`` into the single-string shape this API returns."""
        return " ".join(
            "%s: %s" % (field, message)
            for field, messages in self.errors.items()
            for message in messages
        )
