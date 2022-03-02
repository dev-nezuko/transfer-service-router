from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.gis.geos import Polygon

from .models import Provider, ServiceArea


class ProviderAPITests(APITestCase):
    provider_url = "/testapp/provider/"

    def test_create_provider_success(self):
        payload = {
            "name": "Provider One",
            "email": "provider1@example.com",
            "phone": "+12345678901",
            "language": "English",
            "currency": "USD",
        }

        response = self.client.post(self.provider_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Provider.objects.count(), 1)
        self.assertEqual(Provider.objects.first().email, payload["email"])

    def test_create_provider_rejects_duplicate_email(self):
        Provider.objects.create(
            name="Provider One",
            email="provider1@example.com",
            phone="+12345678901",
            language="English",
            currency="USD",
        )
        payload = {
            "name": "Provider Two",
            "email": "provider1@example.com",
            "phone": "+12345678902",
            "language": "French",
            "currency": "EUR",
        }

        response = self.client.post(self.provider_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_create_provider_rejects_invalid_phone(self):
        payload = {
            "name": "Provider One",
            "email": "provider1@example.com",
            "phone": "not-a-phone",
            "language": "English",
            "currency": "USD",
        }

        response = self.client.post(self.provider_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("phone", response.data)


class ServiceAreaAPITests(APITestCase):
    service_area_url = "/testapp/service_area/"

    def setUp(self):
        self.provider = Provider.objects.create(
            name="Provider One",
            email="provider1@example.com",
            phone="+12345678901",
            language="English",
            currency="USD",
        )

    def test_create_service_area_success(self):
        payload = {
            "name": "Downtown",
            "price": "19.99",
            "provider": self.provider.id,
        }

        response = self.client.post(self.service_area_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ServiceArea.objects.count(), 1)
        self.assertEqual(ServiceArea.objects.first().provider_id, self.provider.id)

    def test_create_service_area_requires_provider(self):
        payload = {
            "name": "Downtown",
            "price": "19.99",
        }

        response = self.client.post(self.service_area_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("provider", response.data)


class SearchServiceAreaAPITests(APITestCase):
    search_url = "/testapp/search_service_area/"

    def setUp(self):
        self.provider = Provider.objects.create(
            name="Provider One",
            email="provider1@example.com",
            phone="+12345678901",
            language="English",
            currency="USD",
        )
        ServiceArea.objects.create(
            name="City Center",
            price="10.00",
            provider=self.provider,
            area_polygon=Polygon(
                (
                    (0.0, 0.0),
                    (0.0, 10.0),
                    (10.0, 10.0),
                    (10.0, 0.0),
                    (0.0, 0.0),
                )
            ),
        )

    def test_search_service_area_returns_match_inside_polygon(self):
        response = self.client.get(self.search_url, {"lat": "5.0", "lng": "5.0"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data["results"]), 1)

    def test_search_service_area_returns_empty_outside_polygon(self):
        response = self.client.get(self.search_url, {"lat": "50.0", "lng": "50.0"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data["results"]), 0)

    def test_search_service_area_rejects_invalid_coordinates(self):
        response = self.client.get(self.search_url, {"lat": "abc", "lng": "5.0"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("message", response.data)
