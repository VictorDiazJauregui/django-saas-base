import os
import sys
import urllib.request

HEALTH_URL = "http://127.0.0.1:8000/api/v1/health/"
FALLBACK_HOST = "localhost"


# Django rejects a Host outside ALLOWED_HOSTS, and inside the container the probe reaches
# 127.0.0.1: it sends the first allowed host instead. ".example.com" also allows example.com.
def read_probe_host(allowed_hosts):
    hosts = (host.strip().lstrip(".") for host in allowed_hosts.split(","))
    return next((host for host in hosts if host and host != "*"), FALLBACK_HOST)


# S310 warns about file: and custom schemes; the URL is the container's own health route.
def is_healthy(url, host, timeout=5):
    request = urllib.request.Request(url, headers={"Host": host})  # noqa: S310
    try:
        with urllib.request.urlopen(request, timeout=timeout) as answer:  # noqa: S310
            return answer.status == 200
    except OSError:
        return False


def probe_exit_code(environ, url=HEALTH_URL):
    host = read_probe_host(environ.get("ALLOWED_HOSTS", ""))
    return 0 if is_healthy(url, host) else 1


# Runs without Django, so the Docker HEALTHCHECK doesn't load the whole project every time.
if __name__ == "__main__":
    sys.exit(probe_exit_code(os.environ))
