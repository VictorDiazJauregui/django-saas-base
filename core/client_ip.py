import ipaddress

from django.conf import settings


def parse_ip_address(candidate):
    try:
        return str(ipaddress.ip_address(candidate.strip()))
    except ValueError:
        return None


# Each trusted proxy appends the address it saw to the right of X-Forwarded-For. Everything
# further left was written by the client, so only the entry added by the outermost trusted
# proxy is reliable.
def select_forwarded_entry(forwarded_for, proxy_count):
    entries = forwarded_for.split(",")
    return entries[-min(proxy_count, len(entries))]


def get_client_ip(request):
    connection_address = request.META.get("REMOTE_ADDR", "")
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    proxy_count = settings.TRUSTED_PROXY_COUNT
    if proxy_count == 0 or not forwarded_for:
        return parse_ip_address(connection_address)
    forwarded_address = parse_ip_address(
        select_forwarded_entry(forwarded_for, proxy_count)
    )
    return forwarded_address or parse_ip_address(connection_address)
