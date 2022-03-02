"""The API_REQUIRE_AUTH authorisation switch.

Default: everything anonymous, which is the surface the assessment describes.
Switched on: reads stay anonymous, writes require an authenticated user.
"""

from django.contrib.auth.models import User
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from testapp.models import Provider
from testapp.tests.factories import make_provider

PROVIDER_URL = "/testapp/provider/"
PAYLOAD = {
    "name": "Provider One",
    "email": "provider1@example.com",
    "phone": "+12345678901",
    "language": "English",
    "currency": "USD",
}


class DefaultOpenApiTests(APITestCase):
    def test_anonymous_writes_are_allowed_by_default(self):
        response = self.client.post(PROVIDER_URL, PAYLOAD, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


@override_settings(API_REQUIRE_AUTH=True)
class RequireAuthTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("staff", password="secret")

    def test_reads_stay_anonymous(self):
        make_provider()

        response = self.client.get(PROVIDER_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_search_stays_anonymous(self):
        response = self.client.get(
            "/testapp/search_service_area/", {"lat": "1", "lng": "1"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_anonymous_create_is_rejected(self):
        response = self.client.post(PROVIDER_URL, PAYLOAD, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Provider.objects.count(), 0)

    def test_anonymous_delete_is_rejected(self):
        provider = make_provider()

        response = self.client.delete("%s%d/" % (PROVIDER_URL, provider.id))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Provider.objects.count(), 1)

    def test_authenticated_create_is_allowed(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(PROVIDER_URL, PAYLOAD, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
