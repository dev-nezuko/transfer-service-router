"""``/testapp/search_service_area/`` — the point-in-polygon endpoint."""

from django.contrib.gis.geos import GEOSGeometry
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from testapp.models import ServiceArea
from testapp.tests.factories import (
    FAR_AWAY_WKT,
    OVERLAPPING_WKT,
    SQUARE_WKT,
    make_provider,
)


class SearchServiceAreaAPITests(APITestCase):
    search_url = "/testapp/search_service_area/"

    def setUp(self):
        self.provider = make_provider()
        self.square = ServiceArea.objects.create(
            name="City Center",
            price="10.00",
            provider=self.provider,
            area_polygon=GEOSGeometry(SQUARE_WKT),
        )

    def test_url_is_reversible(self):
        self.assertEqual(reverse("search_service_area"), self.search_url)

    def test_returns_match_inside_polygon(self):
        response = self.client.get(self.search_url, {"lat": "5.0", "lng": "5.0"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["name"], "City Center")

    def test_returns_empty_outside_polygon(self):
        response = self.client.get(self.search_url, {"lat": "50.0", "lng": "50.0"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_latitude_and_longitude_are_not_swapped(self):
        """(lat=1, lng=12) is outside the square even though (12, 1) is not."""
        ServiceArea.objects.create(
            name="Eastern Strip",
            price="10.00",
            provider=self.provider,
            area_polygon=GEOSGeometry(
                "SRID=4326;POLYGON((11 0, 11 10, 13 10, 13 0, 11 0))"
            ),
        )

        response = self.client.get(self.search_url, {"lat": "1.0", "lng": "12.0"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["name"], "Eastern Strip")

    def test_returns_every_overlapping_area(self):
        ServiceArea.objects.create(
            name="Suburbs",
            price="20.00",
            provider=self.provider,
            area_polygon=GEOSGeometry(OVERLAPPING_WKT),
        )
        ServiceArea.objects.create(
            name="Elsewhere",
            price="30.00",
            provider=self.provider,
            area_polygon=GEOSGeometry(FAR_AWAY_WKT),
        )

        response = self.client.get(self.search_url, {"lat": "7.0", "lng": "7.0"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(
            sorted(item["name"] for item in response.data["results"]),
            ["City Center", "Suburbs"],
        )

    def test_ignores_areas_without_a_polygon(self):
        ServiceArea.objects.create(
            name="No Geometry", price="15.00", provider=self.provider
        )

        response = self.client.get(self.search_url, {"lat": "5.0", "lng": "5.0"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_point_on_the_boundary_is_not_contained(self):
        response = self.client.get(self.search_url, {"lat": "0.0", "lng": "5.0"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_zero_coordinates_are_treated_as_supplied(self):
        """ "0" is falsy-looking but is a valid coordinate, not a missing one."""
        ServiceArea.objects.create(
            name="Null Island",
            price="1.00",
            provider=self.provider,
            area_polygon=GEOSGeometry(
                "SRID=4326;POLYGON((-1 -1, -1 1, 1 1, 1 -1, -1 -1))"
            ),
        )

        response = self.client.get(self.search_url, {"lat": "0", "lng": "0"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["name"], "Null Island")

    def test_results_are_paginated(self):
        for index in range(12):
            ServiceArea.objects.create(
                name="Overlap %02d" % index,
                price="10.00",
                provider=self.provider,
                area_polygon=GEOSGeometry(SQUARE_WKT),
            )

        response = self.client.get(self.search_url, {"lat": "5.0", "lng": "5.0"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 13)
        self.assertEqual(len(response.data["results"]), 10)
        self.assertIsNotNone(response.data["next"])

    def test_missing_both_coordinates_returns_400(self):
        response = self.client.get(self.search_url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("message", response.data)

    def test_missing_longitude_returns_400(self):
        response = self.client.get(self.search_url, {"lat": "5.0"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("message", response.data)

    def test_rejects_invalid_coordinates(self):
        response = self.client.get(self.search_url, {"lat": "abc", "lng": "5.0"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("message", response.data)

    def test_rejects_latitude_out_of_range(self):
        response = self.client.get(self.search_url, {"lat": "120.0", "lng": "5.0"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("lat", response.data["message"])

    def test_rejects_longitude_out_of_range(self):
        response = self.client.get(self.search_url, {"lat": "5.0", "lng": "200.0"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("lng", response.data["message"])

    def test_only_get_is_allowed(self):
        response = self.client.post(self.search_url, {"lat": "5.0", "lng": "5.0"})

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class SearchServiceAreaScalabilityTests(APITestCase):
    """The search endpoint must cost the same whatever it matches."""

    def setUp(self):
        self.provider = make_provider()
        for index in range(15):
            ServiceArea.objects.create(
                name="Overlap %02d" % index,
                price="10.00",
                provider=self.provider,
                area_polygon=GEOSGeometry(SQUARE_WKT),
            )

    def test_search_does_not_issue_one_query_per_match(self):
        with self.assertNumQueries(2):
            response = self.client.get(
                "/testapp/search_service_area/",
                {"lat": "5.0", "lng": "5.0", "page_size": "15"},
            )

        self.assertEqual(len(response.data["results"]), 15)

    def test_results_carry_the_owning_provider(self):
        response = self.client.get(
            "/testapp/search_service_area/", {"lat": "5.0", "lng": "5.0"}
        )

        self.assertEqual(response.data["results"][0]["provider"], self.provider.id)
