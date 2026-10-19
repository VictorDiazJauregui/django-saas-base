from django.core.cache import cache
from django.utils import translation
from rest_framework.test import APITestCase


# Throttling counts requests in the cache, which outlives each test: without a reset, the
# requests of earlier tests use up the limit of later ones.
class CacheResetAPITestCase(APITestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)


# LocaleMiddleware activates the request language on the thread and never deactivates it: after
# a request in Spanish, later tests that read a message outside a request get it in Spanish.
class LanguageResetAPITestCase(CacheResetAPITestCase):
    def setUp(self):
        super().setUp()
        self.addCleanup(translation.deactivate)
