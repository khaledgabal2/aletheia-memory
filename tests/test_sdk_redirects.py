"""Real loopback redirects must never forward SDK credentials or request bodies."""
import asyncio
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading

import pytest

from aletheia.client import AletheiaClient, AletheiaClientError, AsyncAletheiaClient


@contextmanager
def server(handler):
    listener = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    worker = threading.Thread(target=lambda: listener.serve_forever(poll_interval=.01), daemon=True)
    worker.start()
    try:
        yield "http://127.0.0.1:" + str(listener.server_port)
    finally:
        listener.shutdown()
        listener.server_close()
        worker.join(2)


@pytest.mark.parametrize("code", [301, 302, 303, 307, 308])
@pytest.mark.parametrize("method", ["GET", "POST"])
@pytest.mark.parametrize("asynchronous", [False, True])
def test_redirects_never_forward_credentials_or_payload(code, method, asynchronous):
    received, origins = [], []
    class Destination(BaseHTTPRequestHandler):
        def do_GET(self):
            received.append(dict(self.headers))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"data":{"redirected":true}}')
        do_POST = do_GET
        def log_message(self, *args):
            pass
    with server(Destination) as destination:
        class Origin(BaseHTTPRequestHandler):
            def do_GET(self):
                origins.append(self.command)
                self.send_response(code)
                self.send_header("Location", destination + "/capture")
                self.end_headers()
            do_POST = do_GET
            def log_message(self, *args):
                pass
        with server(Origin) as origin:
            client = (AsyncAletheiaClient if asynchronous else AletheiaClient)(origin, "synthetic-bearer", timeout=2)
            with pytest.raises(AletheiaClientError) as failure:
                result = client.health() if method == "GET" else client.retrieve(namespace="test", query="synthetic private body")
                if asynchronous:
                    asyncio.run(result)
            assert failure.value.code == "redirect_blocked"
            assert failure.value.status_code == code
            assert origins == [method], "Redirect rejection must not be retried."
            assert received == [], "No credentials or body may reach the redirect destination."


@pytest.mark.parametrize("method", ["GET", "POST"])
@pytest.mark.parametrize("asynchronous", [False, True])
def test_same_origin_redirects_are_rejected_too(method, asynchronous):
    seen = []
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append(self.path)
            self.send_response(302)
            self.send_header("Location", "/different-path")
            self.end_headers()
        do_POST = do_GET
        def log_message(self, *args):
            pass
    with server(Handler) as origin:
        client = (AsyncAletheiaClient if asynchronous else AletheiaClient)(origin, "synthetic-bearer", timeout=2)
        with pytest.raises(AletheiaClientError) as failure:
            value = client.health() if method == "GET" else client.retrieve(namespace="fixture")
            if asynchronous:
                asyncio.run(value)
        assert failure.value.code == "redirect_blocked"
        assert seen == ["/v1/health" if method == "GET" else "/v1/retrieve"]


@pytest.mark.parametrize("method", ["GET", "POST"])
@pytest.mark.parametrize("asynchronous", [False, True])
def test_direct_requests_still_send_auth_and_preserve_response_metadata(method, asynchronous):
    seen = []
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            seen.append((self.command, self.headers.get("Authorization"), json.loads(body) if body else None))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"data":{"ok":true},"request_id":"synthetic-request","warnings":["fixture"],"pagination":null}')
        do_POST = do_GET
        def log_message(self, *args):
            pass
    with server(Handler) as origin:
        client = (AsyncAletheiaClient if asynchronous else AletheiaClient)(origin, "synthetic-bearer", timeout=2)
        value = client.health() if method == "GET" else client.retrieve(namespace="fixture")
        if asynchronous:
            value = asyncio.run(value)
        assert value == {"ok": True}
        assert client.last_request_id == "synthetic-request"
        assert client.last_warnings == ["fixture"]
        assert seen == [(method, "Bearer synthetic-bearer", None if method == "GET" else {"namespace": "fixture"})]
