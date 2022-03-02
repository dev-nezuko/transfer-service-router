"""``/testapp/provider/`` CRUD, validation and pagination."""

from rest_framework import status
from rest_framework.test import APITestCase

from testapp.models import Provider
from testapp.tests.factories import make_provider


class ProviderAPITests(APITestCase):
    provider_url = "/testapp/provider/"

    def payload(self, **overrides):
        data = {
            "name": "Provider One",
            "email": "provider1@example.com",
            "phone": "+12345678901",
            "language": "English",
            "currency": "USD",
        }
        data.update(overrides)
        return data

    def test_create_provider_success(self):
        response = self.client.post(self.provider_url, self.payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Provider.objects.count(), 1)
        self.assertEqual(Provider.objects.first().email, "provider1@example.com")

    def test_create_provider_rejects_duplicate_email(self):
        make_provider()

        response = self.client.post(
            self.provider_url,
            self.payload(email="provider1@example.com", phone="+12345678902"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_create_provider_rejects_duplicate_phone(self):
        make_provider()

        response = self.client.post(
            self.provider_url,
            self.payload(email="provider2@example.com", phone="+12345678901"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("phone", response.data)

    def test_create_provider_rejects_invalid_phone(self):
        response = self.client.post(
            self.provider_url, self.payload(phone="not-a-phone"), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("phone", response.data)

    def test_create_provider_rejects_invalid_email(self):
        response = self.client.post(
            self.provider_url, self.payload(email="nope"), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_create_provider_requires_every_field(self):
        response = self.client.post(self.provider_url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        for field in ("name", "email", "phone", "language", "currency"):
            self.assertIn(field, response.data)
        self.assertEqual(Provider.objects.count(), 0)

    def test_list_providers_is_paginated(self):
        for index in range(12):
            make_provider(
                email="provider%d@example.com" % index,
                phone="+1234567%04d" % index,
            )

        response = self.client.get(self.provider_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 12)
        self.assertEqual(len(response.data["results"]), 10)
        self.assertIsNotNone(response.data["next"])

    def test_retrieve_provider(self):
        provider = make_provider()

        response = self.client.get("%s%d/" % (self.provider_url, provider.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], provider.email)

    def test_retrieve_unknown_provider_returns_404(self):
        response = self.client.get("%s999999/" % self.provider_url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_provider(self):
        provider = make_provider()

        response = self.client.put(
            "%s%d/" % (self.provider_url, provider.id),
            self.payload(name="Renamed", currency="EUR"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        provider.refresh_from_db()
        self.assertEqual(provider.name, "Renamed")
        self.assertEqual(provider.currency, "EUR")

    def test_update_provider_keeping_its_own_email_is_allowed(self):
        """The UniqueValidator must not flag the instance against itself."""
        provider = make_provider()

        response = self.client.patch(
            "%s%d/" % (self.provider_url, provider.id),
            {"email": provider.email, "name": "Still Fine"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        provider.refresh_from_db()
        self.assertEqual(provider.name, "Still Fine")

    def test_partial_update_provider(self):
        provider = make_provider()

        response = self.client.patch(
            "%s%d/" % (self.provider_url, provider.id),
            {"language": "Spanish"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        provider.refresh_from_db()
        self.assertEqual(provider.language, "Spanish")

    def test_delete_provider(self):
        provider = make_provider()

        response = self.client.delete("%s%d/" % (self.provider_url, provider.id))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Provider.objects.count(), 0)
