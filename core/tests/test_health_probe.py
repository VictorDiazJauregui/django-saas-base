import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from django.test import SimpleTestCase

from core.health_probe import is_healthy, probe_exit_code, read_probe_host


class FakeHealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.server.seen_hosts.append(self.headers["Host"])
        time.sleep(self.server.delay)
        try:
            self.send_response(self.server.status)
            self.end_headers()
            self.wfile.write(b"{}")
        except BrokenPipeError:
            # The probe already gave up waiting: that is what the slow answer test wants.
            return

    def log_message(self, *args):
        pass


class FakeHealthServer:
    def __init__(self, status=200, delay=0):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeHealthHandler)
        self.server.status, self.server.delay, self.server.seen_hosts = (
            status,
            delay,
            [],
        )

    def __enter__(self):
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc_info):
        self.server.shutdown()
        self.server.server_close()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server.server_port}/api/v1/health/"

    @property
    def seen_hosts(self):
        return self.server.seen_hosts


def closed_port_url():
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeHealthHandler)
    port = server.server_port
    server.server_close()
    return f"http://127.0.0.1:{port}/api/v1/health/"


class ProbeHostTests(SimpleTestCase):
    def test_uses_the_first_allowed_host(self):
        self.assertEqual(
            read_probe_host("api.example.com,admin.example.com"), "api.example.com"
        )

    def test_drops_the_leading_dot_of_a_domain_pattern(self):
        self.assertEqual(read_probe_host(".example.com"), "example.com")

    def test_falls_back_to_localhost(self):
        for allowed_hosts in ("", "*", " , "):
            with self.subTest(allowed_hosts=allowed_hosts):
                self.assertEqual(read_probe_host(allowed_hosts), "localhost")


class ProbeTests(SimpleTestCase):
    def test_healthy_answer_is_success(self):
        with FakeHealthServer(200) as server:
            self.assertTrue(is_healthy(server.url, "api.example.com"))

    def test_sends_the_given_host(self):
        with FakeHealthServer(200) as server:
            is_healthy(server.url, "api.example.com")

        self.assertEqual(server.seen_hosts, ["api.example.com"])

    def test_unavailable_answer_is_failure(self):
        with FakeHealthServer(503) as server:
            self.assertFalse(is_healthy(server.url, "api.example.com"))

    def test_refused_connection_is_failure(self):
        self.assertFalse(is_healthy(closed_port_url(), "api.example.com"))

    def test_slow_answer_is_failure(self):
        with FakeHealthServer(200, delay=0.5) as server:
            self.assertFalse(is_healthy(server.url, "api.example.com", timeout=0.1))

    def test_exit_code_reads_allowed_hosts_from_the_environment(self):
        with FakeHealthServer(200) as server:
            environment = {"ALLOWED_HOSTS": "api.example.com"}
            code = probe_exit_code(environment, server.url)

        self.assertEqual(code, 0)
        self.assertEqual(server.seen_hosts, ["api.example.com"])

    def test_exit_code_is_one_when_unhealthy(self):
        with FakeHealthServer(503) as server:
            self.assertEqual(probe_exit_code({}, server.url), 1)
