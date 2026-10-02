import os
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.test import TestCase

from .user_factory import DEFAULT_PASSWORD

User = get_user_model()

ADMIN_EMAIL = "bootstrap.admin@example.com"
ADMIN_ENVIRONMENT = {"ADMIN_EMAIL": ADMIN_EMAIL, "ADMIN_PASSWORD": DEFAULT_PASSWORD}


class CreateAdminAutoCommandTests(TestCase):
    @mock.patch.dict(os.environ, ADMIN_ENVIRONMENT)
    def test_creates_superuser_from_environment(self):
        call_command("create_admin_auto", stdout=mock.Mock())

        admin_user = User.objects.get(email=ADMIN_EMAIL)
        self.assertTrue(admin_user.is_superuser)
        self.assertTrue(admin_user.check_password(DEFAULT_PASSWORD))

    @mock.patch.dict(os.environ, ADMIN_ENVIRONMENT)
    def test_keeps_single_superuser_when_run_twice(self):
        call_command("create_admin_auto", stdout=mock.Mock())
        call_command("create_admin_auto", stdout=mock.Mock())

        self.assertEqual(User.objects.filter(email=ADMIN_EMAIL).count(), 1)

    @mock.patch.dict(os.environ, {**ADMIN_ENVIRONMENT, "ADMIN_PASSWORD": ""})
    def test_requires_credentials_in_environment(self):
        with self.assertRaises(ImproperlyConfigured):
            call_command("create_admin_auto", stdout=mock.Mock())
