from django.conf import settings
from django.core.management import get_commands, load_command_class
from django.test import SimpleTestCase


class RunserverCommandTests(SimpleTestCase):
    def test_project_command_overrides_builtin_runserver(self):
        self.assertEqual(get_commands()["runserver"], "core")

    def test_default_port_comes_from_settings(self):
        command = load_command_class("core", "runserver")

        self.assertEqual(command.default_port, settings.APP_PORT)
