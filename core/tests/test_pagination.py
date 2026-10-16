from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework import serializers, status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.test import APIRequestFactory

User = get_user_model()
USER_COUNT = 130


class UserEmailSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("email",)


class UserListView(ListAPIView):
    queryset = User.objects.order_by("email")
    serializer_class = UserEmailSerializer
    permission_classes = (AllowAny,)


class DefaultPaginationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User.objects.bulk_create(
            User(email=f"user{number:03d}@example.com") for number in range(USER_COUNT)
        )

    def list_users(self, query=""):
        request = APIRequestFactory().get(f"/api/v1/users/{query}")
        response = UserListView.as_view()(request)
        response.render()
        return response

    def test_lists_are_paginated_by_default(self):
        response = self.list_users()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.data), {"count", "next", "previous", "results"})
        self.assertEqual(response.data["count"], USER_COUNT)
        self.assertEqual(len(response.data["results"]), 20)
        self.assertIn("page=2", response.data["next"])
        self.assertIsNone(response.data["previous"])

    def test_page_size_can_be_requested(self):
        response = self.list_users("?page_size=5&page=2")

        self.assertEqual(len(response.data["results"]), 5)
        self.assertEqual(response.data["results"][0]["email"], "user005@example.com")

    def test_page_size_above_the_maximum_is_capped(self):
        response = self.list_users("?page_size=500")

        self.assertEqual(len(response.data["results"]), 100)

    def test_invalid_page_size_falls_back_to_the_default(self):
        for value in ("0", "-3", "abc"):
            with self.subTest(page_size=value):
                response = self.list_users(f"?page_size={value}")

                self.assertEqual(len(response.data["results"]), 20)

    def test_page_out_of_range_is_not_found(self):
        response = self.list_users("?page=999")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "not_found")

    @override_settings(API_PAGE_SIZE=7, API_MAX_PAGE_SIZE=10)
    def test_sizes_are_read_from_the_settings_on_each_request(self):
        default_page = self.list_users()
        capped_page = self.list_users("?page_size=50")

        self.assertEqual(len(default_page.data["results"]), 7)
        self.assertEqual(len(capped_page.data["results"]), 10)
