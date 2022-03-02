"""``/testapp/service_area/`` CRUD, geometry validation and query counts."""

from decimal import Decimal

from django.contrib.gis.geos import GEOSGeometry
from rest_framework import status
from rest_framework.test import APITestCase

from testapp.models import ServiceArea
from testapp.tests.factories import make_provider


class ServiceAreaAPITests(APITestCase):
    service_area_url = "/testapp/service_area/"

    def setUp(self):
        self.provider = make_provider()

    def test_create_service_area_success(self):
        payload = {"name": "Downtown", "price": "19.99", "provider": self.provider.id}

        response = self.client.post(self.service_area_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ServiceArea.objects.count(), 1)
        area = ServiceArea.objects.first()
        self.assertEqual(area.provider_id, self.provider.id)
        self.assertEqual(area.price, Decimal("19.99"))

    def test_create_service_area_with_polygon(self):
        payload = {
            "name": "Downtown",
            "price": "19.99",
            "provider": self.provider.id,
            "area_polygon": {
                "type": "Polygon",
                "coordinates": [[[0, 0], [0, 10], [10, 10], [10, 0], [0, 0]]],
            },
        }

        response = self.client.post(self.service_area_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        area = ServiceArea.objects.get()
        self.assertIsNotNone(area.area_polygon)
        self.assertTrue(area.area_polygon.contains(GEOSGeometry("SRID=4326;POINT(5 5)")))

    def test_create_service_area_requires_provider(self):
        response = self.client.post(
            self.service_area_url, {"name": "Downtown", "price": "19.99"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("provider", response.data)

    def test_create_service_area_rejects_unknown_provider(self):
        payload = {"name": "Downtown", "price": "19.99", "provider": 999999}

        response = self.client.post(self.service_area_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("provider", response.data)
        self.assertEqual(ServiceArea.objects.count(), 0)

    def test_create_service_area_rejects_non_numeric_price(self):
        payload = {"name": "Downtown", "price": "free", "provider": self.provider.id}

        response = self.client.post(self.service_area_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("price", response.data)

    def test_create_service_area_rejects_price_above_field_precision(self):
        """max_digits=6 / decimal_places=2 caps the price at 9999.99."""
        payload = {
            "name": "Downtown",
            "price": "1234567.89",
            "provider": self.provider.id,
        }

        response = self.client.post(self.service_area_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("price", response.data)

    def test_list_service_areas_is_paginated(self):
        for index in range(12):
            ServiceArea.objects.create(
                name="Area %d" % index, price="10.00", provider=self.provider
            )

        response = self.client.get(self.service_area_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 12)
        self.assertEqual(len(response.data["results"]), 10)

    def test_update_service_area_price(self):
        area = ServiceArea.objects.create(
            name="Downtown", price="10.00", provider=self.provider
        )

        response = self.client.patch(
            "%s%d/" % (self.service_area_url, area.id),
            {"price": "42.50"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        area.refresh_from_db()
        self.assertEqual(area.price, Decimal("42.50"))

    def test_delete_service_area(self):
        area = ServiceArea.objects.create(
            name="Downtown", price="10.00", provider=self.provider
        )

        response = self.client.delete("%s%d/" % (self.service_area_url, area.id))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(ServiceArea.objects.count(), 0)


class ServiceAreaGeometryValidationTests(APITestCase):
    """The serializer is the only place a polygon can enter the database."""

    def setUp(self):
        self.provider = make_provider()

    def payload(self, geometry):
        return {
            "name": "Downtown",
            "price": "19.99",
            "provider": self.provider.id,
            "area_polygon": geometry,
        }

    def test_rejects_a_self_intersecting_polygon(self):
        """A bow-tie ring makes every later ST_Contains against it undefined."""
        bowtie = {
            "type": "Polygon",
            "coordinates": [[[0, 0], [10, 10], [10, 0], [0, 10], [0, 0]]],
        }

        response = self.client.post(
            "/testapp/service_area/", self.payload(bowtie), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("area_polygon", response.data)
        self.assertEqual(ServiceArea.objects.count(), 0)

    def test_rejects_a_geometry_that_is_not_a_polygon(self):
        response = self.client.post(
            "/testapp/service_area/",
            self.payload({"type": "Point", "coordinates": [1, 1]}),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("area_polygon", response.data)

    def test_rejects_a_malformed_geometry(self):
        response = self.client.post(
            "/testapp/service_area/", self.payload("not-a-geometry"), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("area_polygon", response.data)

    def test_stored_polygon_is_returned_as_geojson(self):
        geometry = {
            "type": "Polygon",
            "coordinates": [[[0, 0], [0, 10], [10, 10], [10, 0], [0, 0]]],
        }

        created = self.client.post(
            "/testapp/service_area/", self.payload(geometry), format="json"
        )
        response = self.client.get("/testapp/service_area/%d/" % created.data["id"])

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["area_polygon"]["type"], "Polygon")
        self.assertEqual(response.data["area_polygon"]["coordinates"][0][0], [0.0, 0.0])


class ServiceAreaListScalabilityTests(APITestCase):
    """Guards against the two classic list-endpoint regressions."""

    def setUp(self):
        self.provider = make_provider()
        for index in range(20):
            ServiceArea.objects.create(
                name="Area %02d" % index,
                price="10.00",
                provider=self.provider,
                area_polygon=GEOSGeometry(
                    "SRID=4326;POLYGON((0 0, 0 %d, %d %d, %d 0, 0 0))"
                    % (index + 1, index + 1, index + 1, index + 1)
                ),
            )

    def test_listing_does_not_issue_one_query_per_row(self):
        """One COUNT plus one page query, whatever the page size."""
        with self.assertNumQueries(2):
            response = self.client.get("/testapp/service_area/", {"page_size": "20"})

        self.assertEqual(len(response.data["results"]), 20)

    def test_page_size_is_capped(self):
        with self.settings(API_MAX_PAGE_SIZE=5):
            response = self.client.get("/testapp/service_area/", {"page_size": "500"})

        self.assertEqual(len(response.data["results"]), 5)
        self.assertEqual(response.data["count"], 20)
