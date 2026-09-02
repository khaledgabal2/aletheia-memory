"""Read-only first-run inspection. No migration, repair, plugin load or default network call."""
from contextlib import closing
from importlib import metadata
import json
import os
from pathlib import Path
import sqlite3
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, quote
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler
import uuid

from aletheia import Memory
from aletheia.models import ServiceConfig
from aletheia.storage.sqlite import SQLiteStore, SCHEMA_VERSION


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _loopback_url(url):
    parsed = urlparse(url)
    if (parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "::1"}
            or parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment):
        raise ValueError("Use an HTTP(S) URL with a literal loopback address and no credentials, query or fragment.")
    parsed.port  # Validate malformed/out-of-range ports before constructing a request.
    return url.rstrip("/")


def _request(url, *, token=None, payload=None):
    _loopback_url(url)
    headers = {"Accept": "application/json", "Cache-Control": "no-store", "X-Request-ID": uuid.uuid4().hex}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
        headers["X-Aletheia-Contract"] = "memory-read-v1"
    # Never inherit a proxy or forward a credential on redirect.
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    try:
        response = opener.open(Request(url, headers=headers, data=data), timeout=3)
    except HTTPError as error:
        response = error
    with response:
        status = response.status
        if status != 200:
            return status, None  # No untrusted server error text enters diagnostics.
        chunks, size, deadline = [], 0, time.monotonic() + 3
        while True:
            if time.monotonic() >= deadline:
                raise TimeoutError("Diagnostic body deadline")
            chunk = response.read1(min(65536, 1_048_577 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > 1_048_576:
                raise ValueError("Oversized diagnostic response")
        raw = b"".join(chunks)
        return status, json.loads(raw)


class Report:
    def __init__(self):
        self.checks = []

    def add(self, code, status, message, action=None):
        self.checks.append({"code": code, "status": status, "message": message, "next_action": action})

    def result(self):
        statuses = {item["status"] for item in self.checks}
        return {"mode": "read_only", "status": "error" if "error" in statuses else "attention" if "warning" in statuses else "ok",
                "checks": self.checks}


def diagnose(*, db_path=None, namespace="user/default", query=None, config_path=None,
             service_url=None, token_env="ALETHEIA_TOKEN", claim_id=None,
             embedding_provider=None, llm_provider=None, probe_provider=False):
    report = Report()
    if sys.version_info < (3, 11):
        report.add("python_unsupported", "error", "Python 3.11 or newer is required.", "Create a Python 3.11+ environment and reinstall.")
        return report.result()
    report.add("python_supported", "ok", "Python 3.11+ is available.")
    try:
        metadata.version("aletheia-memory")
        report.add("package_installed", "ok", "Memory is installed in this Python environment.")
    except metadata.PackageNotFoundError:
        report.add("package_not_installed", "warning", "Memory source is importable but installed package metadata is missing.", "Install aletheia-memory in the same Python environment.")
    if not namespace or (probe_provider and not (embedding_provider or llm_provider)):
        report.add("invalid_options", "error", "Supply a nonempty namespace and select a provider before probing it.")
        return report.result()
    if service_url:
        # A service-only check never opens a local database or configuration file.
        _service(report, service_url, os.environ.get(token_env), namespace, query, claim_id)
    else:
        try:
            config = ServiceConfig.load(config_path)
        except (OSError, ValueError, TypeError, AttributeError):
            report.add("configuration_invalid", "error", "Configuration is missing, unreadable or invalid.", "Check TOML syntax and setting types; no values are printed or changed.")
            return report.result()
        report.add("configuration_loaded", "ok", "Configuration parsed; no service was started and no settings were changed.")
        if not config.auth_required or config.allow_remote or config.auto_migrate:
            report.add("configuration_review", "warning", "Configuration enables tokenless access, remote binding or automatic migration.", "Review these explicit operator settings before starting a service; diagnostics did not apply them.")
        _database(report, db_path or config.db_path, namespace, query, embedding_provider)
    _providers(report, embedding_provider, llm_provider, probe_provider)
    return report.result()


def _database(report, db_path, namespace, query, embedding_provider):
    path = Path(db_path).expanduser()
    if not path.exists():
        parent = path.parent
        while not parent.exists() and parent != parent.parent:
            parent = parent.parent
        writable = os.access(parent, os.W_OK | os.X_OK)
        report.add("database_missing" if writable else "database_path_unwritable", "error",
                   "No database exists at the selected path." if writable else "The database parent is not writable.",
                   "Choose a writable demo path and explicitly run aletheia init --new --db PATH.")
        return
    if not path.is_file() or not os.access(path, os.R_OK):
        report.add("database_unreadable", "error", "The selected path is not a readable database file.", "Check the path and file permissions.")
        return
    if not os.access(path, os.W_OK) or not os.access(path.parent, os.W_OK | os.X_OK):
        report.add("database_write_unavailable", "warning", "Permissions do not allow normal database writes.", "Choose a writable demo location. No write probe was performed.")
    try:
        with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=.2)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only=ON")
            connection.execute("BEGIN")
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "schema_version" not in tables:
                report.add("schema_missing", "error", "This file has no Memory schema.", "Use a fresh demo path; inspect existing files before any explicit migration.")
                return
            row = connection.execute("SELECT version FROM schema_version WHERE id=1").fetchone()
            version = row[0] if row else None
            if version != SCHEMA_VERSION:
                newer = bool(version and SQLiteStore._version_key(version) > SQLiteStore._version_key(SCHEMA_VERSION))
                report.add("schema_newer" if newer else "migration_required", "error",
                    "The database requires a newer Memory binary." if newer else "The database requires an explicit migration.",
                    "Back up first, then use the matching/newer Memory version." if newer else "Back up first, inspect the migration guide, then explicitly run migrate apply.")
                return
            store = SQLiteStore(str(path), connection)
            required = {"claims", "candidate_claims", "evidence_events", "embeddings", "semantic_index_records"}
            if not required <= tables or not store._schema_current():
                report.add("migration_required", "error", "Required schema objects are missing despite a current version marker.", "Back up and inspect the migration guide; diagnostics will not repair the file.")
                return
            memory = Memory(store, namespace=namespace)
            active = connection.execute("SELECT count(*) FROM claims WHERE namespace=? AND status IN ('active','core')", (namespace,)).fetchone()[0]
            pending = connection.execute("SELECT count(*) FROM candidate_claims WHERE namespace=? AND candidate_status='pending_review'", (namespace,)).fetchone()[0]
            evidence = connection.execute("SELECT count(*) FROM evidence_events WHERE namespace=?", (namespace,)).fetchone()[0]
            report.add("database_ready", "ok", "Database is readable and its schema is current.")
            if pending:
                report.add("pending_review", "warning", f"{pending} candidate(s) await review in the selected namespace.", "Inspect sources and explicitly approve appropriate candidates; pending candidates are not trusted results.")
            if not active:
                report.add("no_trusted_memory" if pending or evidence else "empty_namespace", "warning",
                           "There are no active/core claims in the selected namespace.", "Check the namespace, capture the sample and complete explicit review.")
            elif query is not None:
                hits = memory.retrieve(namespace, query, mode="lexical", limit=1, record_access=False, recompute_confidence=False)
                report.add("lexical_match" if hits else "lexical_no_match", "ok" if hits else "warning",
                           "The lexical query has a trusted match." if hits else "Trusted memory exists, but this lexical query has no match.",
                           None if hits else "Use words present in the sample, such as architecture; lexical search does not promise paraphrase recall.")
            else:
                report.add("trusted_memory_present", "ok", "Trusted memory exists; no query was supplied.")
            stale = connection.execute("SELECT count(*) FROM semantic_index_records WHERE namespace=? AND status NOT IN ('indexed','ready')", (namespace,)).fetchone()[0]
            if stale:
                report.add("semantic_index_stale", "warning", "Stored semantic index records report stale or incomplete state.", "Continue with lexical mode; review the optional semantic setup before an explicit rebuild.")
            if embedding_provider in {"mock", "local_hash", "local_http", "ollama_style", "openai_compatible"}:
                from aletheia.semantic import provider_for_name
                try:
                    provider = provider_for_name(embedding_provider)
                    mismatch = connection.execute("SELECT 1 FROM embeddings WHERE namespace=? AND provider=? AND (dimension<>? OR model<>?) LIMIT 1",
                        (namespace, provider.name, provider.dimension, provider.model)).fetchone()
                    if mismatch:
                        report.add("semantic_index_mismatch", "warning", "Stored model/dimensions differ from the selected provider configuration.", "Select the original configuration or explicitly rebuild after reviewing the semantic guide; no index was changed.")
                except (ValueError, TypeError):
                    pass  # The provider check below reports the configuration error.
    except sqlite3.Error as error:
        code = getattr(error, "sqlite_errorcode", 0) & 255
        report.add("database_locked" if code in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED} else "database_invalid", "error",
                   "Database is busy or exclusively locked." if code in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED} else "Database cannot be inspected safely.",
                   "Let the current writer finish and retry; no repair was attempted." if code in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED} else "Check file format and permissions; retain a backup before any repair.")
    except (OSError, ValueError, TypeError):
        report.add("database_invalid", "error", "Database metadata cannot be inspected safely.", "Check the selected file and schema with the operator; no repair was attempted.")


def _service(report, base_url, token, namespace, query, claim_id):
    try:
        base_url = _loopback_url(base_url)
        if urlparse(base_url).path:
            raise ValueError("Supply the service root, without /v1")
        status, version = _request(base_url + "/v1/version", token=token)
        if status == 401:
            report.add("credentials_invalid", "error", "Credentials are missing, invalid, expired or revoked.", "Supply a valid scoped token through the selected token environment variable.")
            return
        if status != 200:
            report.add("service_http_error", "error", f"Discovery returned HTTP {status}.", "Check the service root, availability and authentication policy.")
            return
        if version.get("data", {}).get("api_version") != "v1":
            report.add("service_incompatible", "error", "The service does not advertise the v1 API.", "Use a compatible Memory service; package-number matching alone is insufficient.")
            return
        status, envelope = _request(base_url + "/v1/auth/me", token=token)
        if status == 401:
            report.add("credentials_invalid", "error", "Credentials are missing, invalid, expired or revoked.", "Supply a valid scoped token through the selected token environment variable.")
            return
        if status == 404:
            report.add("service_legacy", "warning", "This service lacks current-principal discovery.", "Use existing v1 operations only or upgrade; do not assume new profiles or review safety.")
            return
        if status != 200:
            report.add("principal_unavailable", "error", f"Principal discovery returned HTTP {status}.", "Check authentication and service availability.")
            return
        principal = envelope["data"]
        if "memory-read-v1" not in principal.get("supported_profiles", []):
            report.add("profile_missing", "error", "The service lacks memory-read-v1.", "Use a service advertising the required profile; no domain reads were attempted.")
            return
        if not {"memory:read", "memory:admin"} & set(principal["capabilities"]):
            report.add("capability_missing", "error", "The current token lacks memory:read.", "Ask the operator for the required scoped capability; admin is not required.")
            return
        status, result = _request(base_url + "/v1/retrieve", token=token,
            payload={"namespace": namespace, "query": query or "", "mode": "lexical", "limit": 1})
        if status == 403:
            report.add("scope_denied", "error", "The requested namespace or current capability is denied.", "Check the token's namespace grants with the operator; do not broaden to admin.")
            return
        if status != 200:
            report.add("read_unavailable", "error", f"Scoped read returned HTTP {status}.", "Check token expiry, request limits and service availability.")
            return
        report.add("service_read_ready", "ok", "Discovery and an authenticated scoped lexical read succeeded.")
        if not result["data"]:
            report.add("no_visible_matches", "warning", "No authorized lexical match was returned.", "Check query words and operator review status. Empty, hidden and pending memory cannot be distinguished without additional permission.")
        if claim_id:
            status, _ = _request(base_url + "/v1/claims/" + quote(claim_id, safe=""), token=token)
            code = "resource_visible" if status == 200 else "resource_scope_or_privacy_denied" if status == 403 else "resource_missing" if status == 404 else "resource_unavailable"
            report.add(code, "ok" if status == 200 else "warning", f"Selected resource check returned HTTP {status}; no content is printed.",
                       None if status == 200 else "Ask the operator to check resource scope, privacy ceiling and existence. Admin does not bypass privacy.")
    except (URLError, TimeoutError, OSError):
        report.add("service_unavailable", "error", "The service could not be reached within the diagnostic timeout.", "Start the intended local service and check its port; no service was started automatically.")
    except (ValueError, TypeError, KeyError, AttributeError):
        report.add("service_invalid", "error", "The URL or discovery response is not a supported Memory service.", "Use the root HTTP(S) URL with literal 127.0.0.1 or [::1]; redirects and proxies are not followed.")


def _providers(report, embedding_name, llm_name, probe):
    from aletheia.semantic import provider_for_name as embedding_factory
    from aletheia.llm import provider_for_name as llm_factory
    for kind, name, factory in [("embedding", embedding_name, embedding_factory), ("llm", llm_name, llm_factory)]:
        if not name:
            report.add(kind + "_optional", "ok", "No optional provider selected; zero-model lexical memory is available.")
            continue
        if name not in {"mock", "local_hash", "local_http", "ollama_style", "openai_compatible"} or (kind == "llm" and name == "local_hash"):
            report.add(kind + "_configuration_invalid", "warning", "Unknown diagnostic provider type; no plugin was loaded.", "Choose a documented built-in provider. Lexical mode still works.")
            continue
        try:
            provider = factory(name)
            endpoint = getattr(provider, "endpoint", None)
            if endpoint is not None and (not endpoint or not provider.model or (kind == "embedding" and provider.dimension <= 0)):
                raise ValueError("Incomplete provider configuration")
            if not probe or endpoint is None:
                report.add(kind + "_configured", "ok", "Provider configuration is present; no network/model call was made.", "Use --probe-provider for an explicit local endpoint reachability check; model quality/output remains a separate smoke test." if endpoint else None)
                continue
            status, _ = _request(endpoint, token=getattr(provider, "api_key", None))
            suffix = "_unavailable" if status >= 500 else "_http_error" if status >= 300 else "_reachable"
            report.add(kind + suffix, "warning" if status >= 300 else "ok",
                       f"Provider endpoint returned HTTP {status}. No model input was submitted.",
                       "Inspect provider logs/configuration and perform the optional recipe smoke test; reachability alone does not validate a model.")
        except (URLError, TimeoutError, OSError):
            report.add(kind + "_unavailable", "warning", "Optional provider endpoint is unreachable.", "Start the intended local provider or continue using lexical mode.")
        except (ValueError, TypeError):
            report.add(kind + "_configuration_invalid", "warning", "Optional provider settings or endpoint response are invalid for this diagnostic.", "Check endpoint/model/dimensions without exposing secrets. Probes support literal loopback addresses only; lexical mode still works.")
