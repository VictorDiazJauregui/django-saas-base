from django.conf import settings
from django.contrib.auth.hashers import get_hasher
from django.test import SimpleTestCase


class FastPasswordHashingTestRunnerTests(SimpleTestCase):
    def test_the_suite_hashes_passwords_with_the_fast_hasher(self):
        self.assertEqual(get_hasher().algorithm, "md5")

    def test_the_project_runs_its_tests_with_that_runner(self):
        self.assertEqual(
            settings.TEST_RUNNER, "core.test_runner.FastPasswordHashingTestRunner"
        )
