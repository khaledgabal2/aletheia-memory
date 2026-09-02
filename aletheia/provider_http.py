"""Optional loopback-only provider transport; never follows redirects or proxies."""
import ipaddress
from urllib.parse import urlparse
from urllib.request import build_opener, HTTPRedirectHandler, ProxyHandler


def validate_local_endpoint(endpoint):
    parsed = urlparse(endpoint)
    try:
        local = ipaddress.ip_address(parsed.hostname or "").is_loopback
        port = parsed.port
    except ValueError:
        local, port = False, None
    if parsed.scheme != "http" or not local or not port or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("Local-only providers require an explicit http:// loopback IP and port, without credentials or a fragment.")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def local_opener(endpoint):
    validate_local_endpoint(endpoint)
    class LocalOnlyOpener:
        def __init__(self):
            self.opener = build_opener(ProxyHandler({}), NoRedirect())
        def open(self, request, **kwargs):
            validate_local_endpoint(request.full_url if hasattr(request, "full_url") else request)
            return self.opener.open(request, **kwargs)
    return LocalOnlyOpener()
