"""Seed a small, realistic dataset so the API is never empty on first boot."""

from django.contrib.gis.geos import GEOSGeometry
from django.core.management.base import BaseCommand
from django.db import transaction

from testapp.models import Provider, ServiceArea


def box(min_lng, min_lat, max_lng, max_lat):
    """WKT for an axis-aligned box, in WGS 84 (lng/lat order)."""
    return (
        "SRID=4326;POLYGON((%(x0)s %(y0)s, %(x0)s %(y1)s, %(x1)s %(y1)s, "
        "%(x1)s %(y0)s, %(x0)s %(y0)s))"
        % {"x0": min_lng, "y0": min_lat, "x1": max_lng, "y1": max_lat}
    )


# Provider natural keys. Email is what the importer and this command upsert on.
AURORA = "ops@auroratransfers.example"
PRIME = "ops@lisboaprime.example"
RHEINLAND = "ops@rheinlandrides.example"
HUDSON = "ops@hudsonshuttle.example"

PROVIDERS = [
    {
        "email": AURORA,
        "name": "Aurora Transfers",
        "phone": "+351210000001",
        "language": "Portuguese",
        "currency": "EUR",
    },
    {
        "email": PRIME,
        "name": "Lisboa Prime Cars",
        "phone": "+351210000002",
        "language": "Portuguese",
        "currency": "EUR",
    },
    {
        "email": RHEINLAND,
        "name": "Rheinland Rides",
        "phone": "+493010000003",
        "language": "German",
        "currency": "EUR",
    },
    {
        "email": HUDSON,
        "name": "Hudson Shuttle",
        "phone": "+12125550004",
        "language": "English",
        "currency": "USD",
    },
]

# Three of the Lisbon areas deliberately overlap around the city centre, so the
# search endpoint returns more than one row for a single coordinate.
SERVICE_AREAS = [
    (AURORA, "Lisbon City", "24.50", box(-9.25, 38.68, -9.05, 38.80)),
    (AURORA, "Lisbon Airport Run", "31.00", box(-9.16, 38.74, -9.10, 38.80)),
    (PRIME, "Lisbon Centre Premium", "58.75", box(-9.20, 38.70, -9.10, 38.76)),
    (PRIME, "Cascais Coast", "72.00", box(-9.48, 38.66, -9.32, 38.74)),
    (RHEINLAND, "Berlin Inner Ring", "29.90", box(13.25, 52.45, 13.55, 52.60)),
    (RHEINLAND, "Brandenburg Airport", "44.00", box(13.47, 52.33, 13.58, 52.42)),
    (HUDSON, "Manhattan", "65.00", box(-74.02, 40.70, -73.91, 40.88)),
    (HUDSON, "JFK Corridor", "89.50", box(-73.83, 40.62, -73.74, 40.68)),
]


class Command(BaseCommand):
    help = "Create a demo set of providers and overlapping service areas."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete existing providers and service areas first.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["flush"]:
            ServiceArea.objects.all().delete()
            Provider.objects.all().delete()

        providers = {}
        for record in PROVIDERS:
            provider, _ = Provider.objects.update_or_create(
                email=record["email"],
                defaults={k: v for k, v in record.items() if k != "email"},
            )
            providers[provider.email] = provider

        for email, name, price, wkt in SERVICE_AREAS:
            ServiceArea.objects.update_or_create(
                provider=providers[email],
                name=name,
                defaults={"price": price, "area_polygon": GEOSGeometry(wkt)},
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Seeded %d providers and %d service areas."
                % (Provider.objects.count(), ServiceArea.objects.count())
            )
        )
        self.stdout.write("Try: /testapp/search_service_area/?lat=38.7369&lng=-9.1399")
