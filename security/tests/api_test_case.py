from django.core.cache import cache
from rest_framework.test import APITestCase


# Throttling counts requests in the cache, which outlives each test: without a reset, the
# requests of earlier tests use up the limit of later ones.
class CacheResetAPITestCase(APITestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)
