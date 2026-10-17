import re
from pathlib import Path

from django.test import SimpleTestCase

PROJECT_ROOT = Path(__file__).resolve().parents[2]
POSTGRES_IMAGE = re.compile(r"image:\s*(postgres:\S+)")
PINNED_MINOR = re.compile(r"^postgres:\d+\.\d+-alpine$")


def postgres_images(relative_path):
    return POSTGRES_IMAGE.findall((PROJECT_ROOT / relative_path).read_text())


# Compose and the CI must run the same PostgreSQL, or a test can pass in one and fail in the
# other. Raising the version means editing both files.
class PostgresImageTests(SimpleTestCase):
    def test_compose_and_ci_use_the_same_image(self):
        compose = postgres_images("docker-compose.yml")
        ci = postgres_images(".github/workflows/ci.yml")

        self.assertEqual(len(compose), 1)
        self.assertEqual(compose, ci)

    def test_image_pins_the_minor_version(self):
        self.assertRegex(postgres_images("docker-compose.yml")[0], PINNED_MINOR)
