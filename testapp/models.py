from django.contrib.gis.db import models as gis_models
from django.db import models
from django.core.validators import RegexValidator

phone_regex = RegexValidator(
    regex=r"^\+?1?\d{9,15}$",
    message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.",
)

class Provider(models.Model):
    name = models.CharField(max_length=60)
    email = models.EmailField(max_length=254, unique=True)
    phone = models.CharField(validators=[phone_regex], max_length=17, blank=True, unique=True)
    language = models.CharField(max_length=30)
    currency = models.CharField(max_length=30)

    def __str__(self):
        return self.name

class ServiceArea(models.Model):
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

    def __str__(self):
        return self.name

