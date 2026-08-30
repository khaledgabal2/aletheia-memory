"""Memory-owned read schema/client/browser checks, using disposable databases only."""

import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import tempfile
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from openapi_spec_validator import validate
from aletheia.service.read_contracts import read_document
from scripts.v1_4_phase0 import ROOT, NAMESPACE, local_service, request


def domain_state(memory):
    # Credentials and operational HTTP counters are fixture/transport state, not
    # domain writes. Compare every other table, including indexes and snapshots.
    excluded = {"service_request_log", "rate_limit_records", "api_clients", "api_tokens", "capability_grants", "namespace_access_grants"}
    result = {}
    for row in memory.store.connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
        name = row[0]
        if name in excluded:
            continue
        rows = sorted(repr(tuple(item)) for item in memory.store.connection.execute('SELECT * FROM "' + name.replace('"', '""') + '"'))
        result[name] = hashlib.sha256(repr(rows).encode()).hexdigest()
    return result


def browser_server(service, upstream, claim):
    before = domain_state(service.memory)
    state = {}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, status, body, content_type="application/json", headers=None):
            raw = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            for name, value in (headers or {}).items():
                self.send_header(name, value)
            self.end_headers()
            try:
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_GET(self):
            self.handle_request()

        def do_POST(self):
            self.handle_request()

        def handle_request(self):
            authority = f"127.0.0.1:{self.server.server_port}"
            if self.headers.get("Host") != authority or self.headers.get("Origin", "http://" + authority) != "http://" + authority:
                self.reply(403, {"error": "Fixture is restricted to its same-origin loopback page."})
                return
            path = urlparse(self.path).path
            try:
                length = int(self.headers.get("Content-Length", 0))
            except ValueError:
                self.reply(400, {"error": "Invalid Content-Length"}); return
            if length > 65536 or length < 0:
                self.reply(413, {"error": "Fixture request too large"}); return
            body = self.rfile.read(length) if length else None
            if path == "/fixture" and self.command == "POST":
                action = json.loads(body or b"{}").get("action")
                with service.lock:
                    if action == "connect":
                        if "token_id" in state:
                            service.auth.revoke_token(state["token_id"])
                        client = service.auth.create_client(name="Disposable browser fixture", client_type="test")
                        token, raw = service.auth.create_token(client_id=client.id, capabilities=["memory:read", "memory:context", "memory:audit"], namespace_grants=[NAMESPACE])
                        state.update(token_id=token.id)
                        self.reply(200, {"token": raw, "claim_id": claim.id}); return
                    if action == "revoke" and "token_id" in state:
                        service.auth.revoke_token(state["token_id"])
                    elif action == "narrow" and "token_id" in state:
                        with service.memory.store.transaction():
                            service.memory.store.connection.execute("UPDATE api_tokens SET privacy_ceiling='public' WHERE id=?", (state["token_id"],))
                    else:
                        self.reply(400, {"error": "Unknown fixture action"}); return
                self.reply(200, {"ok": True}); return
            if path == "/fixture-stats" and self.command == "GET":
                with service.lock:
                    self.reply(200, {"domain_unchanged": before == domain_state(service.memory)})
                return
            static = {"/": ROOT / "contracts/typescript/browser.html",
                      "/assets/read-client.js": ROOT / "contracts/typescript/dist/read-client.js",
                      "/vendor/openapi-fetch.js": ROOT / "contracts/typescript/node_modules/openapi-fetch/dist/index.mjs"}
            if path in static and self.command == "GET":
                self.reply(200, static[path].read_bytes(), "text/html; charset=utf-8" if path == "/" else "text/javascript; charset=utf-8")
                return
            if path.startswith("/v1/"):
                # Fixed upstream, bounded body, explicit forwarding allowlist.
                # The proxy verifies its own Origin before removing that header.
                headers = {key: self.headers[key] for key in ["Authorization", "Content-Type", "X-Request-ID", "X-Aletheia-Contract"] if key in self.headers}
                forwarded = Request(upstream + self.path, data=body, headers=headers, method=self.command)
                try:
                    response = urlopen(forwarded, timeout=10)
                except HTTPError as error:
                    response = error
                with response:
                    self.reply(response.status, response.read(), response.headers.get("Content-Type", "application/json"),
                               {key: response.headers[key] for key in ["X-Request-ID", "Retry-After"] if key in response.headers})
                return
            self.reply(404, {"error": "Unknown fixture resource"})
    return ThreadingHTTPServer(("127.0.0.1", 0), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--typescript", action="store_true")
    parser.add_argument("--browser", action="store_true")
    args = parser.parse_args()
    if not any([args.output, args.typescript, args.browser]):
        parser.error("choose --output, --typescript or --browser")
    with tempfile.TemporaryDirectory(prefix="aletheia-read-") as directory:
        with local_service(directory) as (service, url, tokens):
            claim = service.memory.remember(namespace=NAMESPACE, memory_type="preference", subject="user", predicate="prefers",
                                            object="careful architecture notes", confidence=.95)
            document = read_document(request(url, "GET", "/v1/openapi.json")["body"]["data"])
            validate(document)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
                print("Validated discovery, six read operations and two aliases from the running service.", flush=True)
            if args.typescript:
                env = {**os.environ, "ALETHEIA_TEST_URL": url, "ALETHEIA_TEST_TOKEN": tokens["agent"], "ALETHEIA_TEST_CLAIM": claim.id}
                subprocess.run(["node", "dist/read.js"], cwd=ROOT / "contracts/typescript", env=env, check=True, timeout=30)
            if args.browser:
                proxy = browser_server(service, url, claim)
                print(f"Disposable same-origin browser fixture: http://127.0.0.1:{proxy.server_port}/", flush=True)
                try:
                    proxy.serve_forever()
                except KeyboardInterrupt:
                    pass
                finally:
                    proxy.server_close()


if __name__ == "__main__":
    main()
