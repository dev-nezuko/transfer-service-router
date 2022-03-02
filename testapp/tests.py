from rest_framework import status
from rest_framework.test import APITestCase

from .models import Provider


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
