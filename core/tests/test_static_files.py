import shutil
import tempfile

from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.management import call_command
from django.test import SimpleTestCase, override_settings

MANIFEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}


# What a deployment does: collectstatic into STATIC_ROOT, then whitenoise serves the files
# itself, with DEBUG=False and no runserver.
class StaticFilesServingTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.static_root = tempfile.mkdtemp(prefix="dsb-static-")
        cls.addClassCleanup(shutil.rmtree, cls.static_root)
        cls.settings_override = override_settings(
            STATIC_ROOT=cls.static_root,
            STORAGES=MANIFEST_STORAGES,
            WHITENOISE_AUTOREFRESH=False,
        )
        cls.settings_override.enable()
        cls.addClassCleanup(cls.settings_override.disable)
        call_command("collectstatic", interactive=False, verbosity=0)

    # whitenoise answers with an open file: closing it keeps the test run free of warnings.
    def fetch(self, url, **headers):
        response = self.client.get(url, **headers)
        self.addCleanup(response.close)
        return response

    def test_serves_the_hashed_admin_stylesheet(self):
        url = staticfiles_storage.url("admin/css/base.css")
        response = self.fetch(url)

        self.assertRegex(url, r"^/static/admin/css/base\.[0-9a-f]{12}\.css$")
        self.assertEqual(response.status_code, 200)
        self.assertIn("immutable", response["Cache-Control"])

    def test_serves_a_compressed_copy_to_clients_that_accept_it(self):
        url = staticfiles_storage.url("admin/css/base.css")
        response = self.fetch(url, HTTP_ACCEPT_ENCODING="gzip")

        self.assertEqual(response["Content-Encoding"], "gzip")

    def test_admin_pages_link_the_hashed_files(self):
        response = self.client.get("/admin/login/")

        self.assertContains(response, staticfiles_storage.url("admin/css/base.css"))
