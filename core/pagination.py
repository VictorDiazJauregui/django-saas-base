from django.conf import settings
from rest_framework.pagination import PageNumberPagination


class ConfigurablePageNumberPagination(PageNumberPagination):
    """Lets the client pick ?page_size= up to API_MAX_PAGE_SIZE.

    DRF copies PAGE_SIZE into the class at import time, so both sizes are read from the
    settings on every request instead (override_settings in tests reaches them).
    """

    page_size_query_param = "page_size"

    @property
    def page_size(self):
        return settings.API_PAGE_SIZE

    @property
    def max_page_size(self):
        return settings.API_MAX_PAGE_SIZE
