import ipaddress
import socket
from urllib.parse import urlsplit

ALLOWED_SCHEMES = ("http", "https")


class UnsafeWebhookUrl(Exception):
    pass


def resolve_addresses(host, port):
    try:
        found = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as error:
        raise UnsafeWebhookUrl(f"{host} does not resolve.") from error
    return {ipaddress.ip_address(entry[4][0]) for entry in found}


def is_public_address(address):
    return address.is_global and not address.is_multicast


# Without this, whoever adds an endpoint could make the server call its own network or the
# cloud metadata service and read the status code back in the admin.
def validate_destination(url, allow_private):
    parts = urlsplit(url)
    if parts.scheme not in ALLOWED_SCHEMES or not parts.hostname:
        raise UnsafeWebhookUrl("Only http and https URLs with a host are allowed.")
    if allow_private:
        return
    port = parts.port or (443 if parts.scheme == "https" else 80)
    addresses = resolve_addresses(parts.hostname, port)
    if not all(is_public_address(address) for address in addresses):
        raise UnsafeWebhookUrl(f"{parts.hostname} resolves to a private address.")
