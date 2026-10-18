from django.test import RequestFactory, SimpleTestCase, override_settings

from core.client_ip import get_client_ip

CONNECTION_ADDRESS = "192.0.2.10"


def build_request(forwarded_for=None):
    headers = {"REMOTE_ADDR": CONNECTION_ADDRESS}
    if forwarded_for is not None:
        headers["HTTP_X_FORWARDED_FOR"] = forwarded_for
    return RequestFactory().post("/", **headers)


@override_settings(TRUSTED_PROXY_COUNT=0)
class WithoutTrustedProxiesTests(SimpleTestCase):
    def test_ignores_the_forwarded_header(self):
        request = build_request("8.8.8.8")

        self.assertEqual(get_client_ip(request), CONNECTION_ADDRESS)

    def test_uses_the_connection_address_without_header(self):
        self.assertEqual(get_client_ip(build_request()), CONNECTION_ADDRESS)


class WithTrustedProxiesTests(SimpleTestCase):
    @override_settings(TRUSTED_PROXY_COUNT=1)
    def test_takes_the_last_entry_with_one_proxy(self):
        request = build_request("8.8.8.8, 203.0.113.9")

        self.assertEqual(get_client_ip(request), "203.0.113.9")

    @override_settings(TRUSTED_PROXY_COUNT=2)
    def test_takes_the_nth_entry_from_the_right(self):
        request = build_request("8.8.8.8, 203.0.113.9, 10.0.0.1")

        self.assertEqual(get_client_ip(request), "203.0.113.9")

    @override_settings(TRUSTED_PROXY_COUNT=3)
    def test_takes_the_leftmost_entry_when_there_are_fewer_than_proxies(self):
        request = build_request("203.0.113.9, 10.0.0.1")

        self.assertEqual(get_client_ip(request), "203.0.113.9")

    @override_settings(TRUSTED_PROXY_COUNT=1)
    def test_ignores_whitespace_around_the_entry(self):
        request = build_request("8.8.8.8 ,  203.0.113.9 ")

        self.assertEqual(get_client_ip(request), "203.0.113.9")

    @override_settings(TRUSTED_PROXY_COUNT=1)
    def test_accepts_ipv6_entries(self):
        request = build_request("2001:db8::1")

        self.assertEqual(get_client_ip(request), "2001:db8::1")

    @override_settings(TRUSTED_PROXY_COUNT=1)
    def test_falls_back_to_the_connection_address_for_an_invalid_entry(self):
        request = build_request("8.8.8.8, not-an-ip")

        self.assertEqual(get_client_ip(request), CONNECTION_ADDRESS)

    @override_settings(TRUSTED_PROXY_COUNT=1)
    def test_falls_back_to_the_connection_address_without_header(self):
        self.assertEqual(get_client_ip(build_request()), CONNECTION_ADDRESS)
