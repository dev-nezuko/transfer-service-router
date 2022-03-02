"""Model-level behaviour: constraints, relations and geometry round-tripping."""

from django.contrib.gis.geos import GEOSGeometry
from django.db import IntegrityError, transaction
from rest_framework.test import APITestCase

from testapp.models import Provider, ServiceArea
from testapp.tests.factories import SQUARE_WKT, make_provider


class ProviderModelTests(APITestCase):
    def test_str_returns_name(self):
        provider = make_provider(name="Acme Transfers")

        self.assertEqual(str(provider), "Acme Transfers")

    def test_email_must_be_unique(self):
        make_provider()

        with self.assertRaises(IntegrityError), transaction.atomic():
            make_provider(email="provider1@example.com", phone="+12345678902")

    def test_phone_must_be_unique(self):
        make_provider()

        with self.assertRaises(IntegrityError), transaction.atomic():
            make_provider(email="provider2@example.com", phone="+12345678901")

    def test_multiple_providers_may_omit_the_phone_number(self):
        """phone is optional, so more than one row may leave it unset.

        This only holds because the column is nullable; a blank-but-not-null
        unique CharField would collide on the second empty string.
        """
        make_provider(email="a@example.com", phone=None)
        make_provider(email="b@example.com", phone=None)

        self.assertEqual(Provider.objects.filter(phone__isnull=True).count(), 2)


class ServiceAreaModelTests(APITestCase):
    def setUp(self):
        self.provider = make_provider()

    def test_str_returns_name(self):
        area = ServiceArea.objects.create(name="Downtown", price="10.00")

        self.assertEqual(str(area), "Downtown")

    def test_related_name_exposes_areas_on_the_provider(self):
        ServiceArea.objects.create(name="Downtown", price="10.00", provider=self.provider)
        ServiceArea.objects.create(name="Airport", price="25.00", provider=self.provider)

        self.assertEqual(self.provider.service_areas.count(), 2)

    def test_deleting_a_provider_cascades_to_its_service_areas(self):
        ServiceArea.objects.create(name="Downtown", price="10.00", provider=self.provider)

        self.provider.delete()

        self.assertEqual(ServiceArea.objects.count(), 0)

    def test_polygon_round_trips_through_the_database(self):
        area = ServiceArea.objects.create(
            name="Downtown",
            price="10.00",
            provider=self.provider,
            area_polygon=GEOSGeometry(SQUARE_WKT),
        )

        area.refresh_from_db()

        self.assertEqual(area.area_polygon.srid, 4326)
        self.assertEqual(area.area_polygon.num_points, 5)
