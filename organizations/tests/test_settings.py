from django.test import SimpleTestCase

from core.tests.settings_subprocess import read_settings


class TenancySettingsTests(SimpleTestCase):
    def test_off_unless_the_environment_turns_it_on(self):
        self.assertEqual(read_settings(["TENANCY_ENABLED"]), {"TENANCY_ENABLED": False})

    def test_the_environment_turns_it_on(self):
        settings = read_settings(["TENANCY_ENABLED"], TENANCY_ENABLED="True")
        self.assertEqual(settings, {"TENANCY_ENABLED": True})
