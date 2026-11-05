from django.test.runner import DiscoverRunner
from django.test.utils import override_settings

FAST_PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


# The production hasher takes about 0.3 s per password on purpose, and most tests create
# users: the suite spent minutes hashing. No test measures the strength of the hash.
class FastPasswordHashingTestRunner(DiscoverRunner):
    def setup_test_environment(self, **kwargs) -> None:
        super().setup_test_environment(**kwargs)
        self.fast_hashing = override_settings(PASSWORD_HASHERS=FAST_PASSWORD_HASHERS)
        self.fast_hashing.enable()

    def teardown_test_environment(self, **kwargs) -> None:
        self.fast_hashing.disable()
        super().teardown_test_environment(**kwargs)
