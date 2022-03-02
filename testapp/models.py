"""Domain models: transfer providers and the priced polygons they serve."""

from django.contrib.gis.db import models as gis_models
from django.core.validators import RegexValidator
from django.db import models

phone_regex = RegexValidator(
    regex=r"^\+?1?\d{9,15}$",
    message=(
        "Phone number must be entered in the format: '+999999999'. "
        "Up to 15 digits allowed."
    ),
)


class Provider(models.Model):
    """A company that operates transfers inside one or more service areas."""

    name = models.CharField(max_length=60)
    email = models.EmailField(max_length=254, unique=True)
    # NULL (rather than "") is used for "no phone number" so that the unique
    # constraint does not collide for every provider without a phone.
    phone = models.CharField(
        validators=[phone_regex], max_length=17, blank=True, null=True, unique=True
    )
    language = models.CharField(max_length=30)
    currency = models.CharField(max_length=30)

    class Meta:
        # A deterministic default ordering: any queryset that reaches the
        # paginator without an explicit order_by still pages consistently.
        ordering = ("id",)

    def __str__(self):
        return self.name


class ServiceArea(models.Model):
    """A polygon a provider serves, with the price charged inside it.

    ``area_polygon`` is a WGS 84 ``PolygonField``; GeoDjango gives it a GiST
    index by default (migration ``0007``), which is what makes the
    point-in-polygon search in :mod:`testapp.queries` scale.
    """

    name = models.CharField(max_length=60)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    area_polygon = gis_models.PolygonField(blank=True, null=True)
    provider = models.ForeignKey(
        Provider,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="service_areas",
    )

    class Meta:
        ordering = ("id",)

    def __str__(self):
        return self.name
