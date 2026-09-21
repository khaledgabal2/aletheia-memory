"""Behavioral probes for the bundled SDK loop, with disposable synthetic data.

Only code whose AST matches the bundled contract is executed. This is a narrow
contract verifier, not a sandbox for arbitrary third-party Python adapters.
"""
from __future__ import annotations

import ast
from contextlib import closing
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace


CONTRACT = "bundled-sdk-loop-v1"
ADAPTER_TYPES = {"python-sdk", "generic-http", "mcp-client"}


def _body(tree):
    # Scaffold labels and module documentation do not alter executable behavior.
    if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant) and isinstance(tree.body[0].value.value, str):
        tree.body = tree.body[1:]
    return ast.dump(tree, include_attributes=False)


def check_adapter(path, reference_source, *, expected_type=None):
    details = {"assurance": "structural", "contract": CONTRACT, "probes": {}}
    results = {}
    try:
        target = Path(path)
        files = [target / name for name in ("README.md", "aletheia-adapter.json", "agent_loop.py")]
        if any(not item.is_file() or item.is_symlink() or item.stat().st_size > 256_000 for item in files):
            raise ValueError("Adapter requires regular README, manifest and Python files under 256 KB each.")
        manifest = json.loads(files[1].read_text(encoding="utf-8"))
        if (not isinstance(manifest, dict) or manifest.get("type") not in ADAPTER_TYPES
            or (expected_type is not None and manifest["type"] != expected_type)):
            raise ValueError("Adapter manifest type is missing, unsupported, or differs from the requested certificate.")
        source = files[2].read_text(encoding="utf-8")
        tree = ast.parse(source, filename="agent_loop.py")
        code = compile(tree, "agent_loop.py", "exec")  # Also rejects return/break outside a function/loop.
        details.update(source_sha256=hashlib.sha256(source.encode()).hexdigest(), adapter_type=manifest["type"])
        results["contract_registered"] = ("structural_passed", "README, manifest and Python syntax checked.")
        if _body(tree) != _body(ast.parse(reference_source)):
            message = "Custom adapter behavior is unverified. Only the bundled SDK loop contract has an executable probe."
            results.update(governance_preserved=("skipped", message), error_envelope=("skipped", message))
            return results, details
        probes = _probe_bundled_loop(code)
        details.update(assurance="behavioral", probes=probes)
        results = {
            "contract_registered": ("passed", "Bundled SDK loop returned the isolated fixture's context."),
            "governance_preserved": ("passed", "Observed one candidate with evidence, zero active writes, and namespace/privacy exclusions."),
            "error_envelope": ("passed", "Permission errors propagated and denied writes preserved memory state."),
        }
    except (OSError, ValueError, SyntaxError, UnicodeError, RecursionError):
        # Do not echo arbitrary source, paths, or parser excerpts in service reports.
        results = {name: ("failed", "Adapter structure or Python compilation failed.")
                   for name in ("contract_registered", "governance_preserved", "error_envelope")}
    except Exception:  # A failing contract must yield failed evidence, never a certificate.
        results = {name: ("failed", "Bundled adapter behavioral probe failed.")
                   for name in ("contract_registered", "governance_preserved", "error_envelope")}
    return results, details


def _probe_bundled_loop(code):
    from aletheia import Memory
    from aletheia.client import AletheiaClient, AletheiaForbiddenError
    from aletheia.models import ServiceConfig
    from aletheia.service.http import AletheiaService

    namespace = "certification/fixture"
    query = "certneedle λ"
    with tempfile.TemporaryDirectory(prefix="aletheia-adapter-contract-") as root, closing(
        Memory.open(str(Path(root) / "fixture.db"), namespace=namespace)
    ) as memory:
        public = memory.remember(memory_type="fact", subject="certneedle", predicate="records", object="fixture context λ")
        secret = memory.remember(memory_type="fact", subject="certneedle private", predicate="records",
                                 object="PRIVATE_CONTRACT_SENTINEL", privacy_level="secret")
        service = AletheiaService(memory, ServiceConfig(db_path=memory.store.path, rate_limit_enabled=False))
        principal = service.auth.create_client(name="isolated contract fixture", client_type="test")

        def token(capabilities):
            return service.auth.create_token(client_id=principal.id, capabilities=capabilities,
                namespace_grants=[namespace], privacy_ceiling="personal")[1]

        allowed = token(["memory:read", "memory:context", "memory:write_candidate"])
        read_only = token(["memory:read", "memory:context"])
        calls = []

        class FixtureClient(AletheiaClient):
            def _request(self, method, path, payload=None, **kwargs):
                # Exercise the real SDK methods and service boundary, without sockets.
                calls.append((method, path, payload))
                status, envelope = service.handle_http(method=method, path=path,
                    headers={"Authorization": f"Bearer {self.token}"},
                    body=json.dumps(payload).encode() if payload is not None else b"")
                if status >= 400:
                    self._raise_error(envelope, status)
                return envelope["data"]

        def import_client(name, *args, **kwargs):
            if name != "aletheia.client":
                raise RuntimeError("Unexpected import in the verified loop.")
            return SimpleNamespace(AletheiaClient=FixtureClient)

        scope = {"__builtins__": {"__import__": import_client, "str": str}}
        exec(code, scope)  # Executable AST was checked against our bundled source above.
        run_once = scope["run_once"]
        markdown = run_once("http://fixture.invalid", allowed, namespace, query)
        candidates = memory.list_candidates(namespace)
        if (not isinstance(markdown, str) or "fixture context" not in markdown or "PRIVATE_CONTRACT_SENTINEL" in markdown
            or len(candidates) != 1 or candidates[0].candidate_status != "pending_review"
            or candidates[0].namespace != namespace or candidates[0].object != query
            or not candidates[0].evidence_ids or not candidates[0].evidence_spans
            or {claim.id for claim in memory.list_claims(namespace=namespace)} != {public.id, secret.id}
            or [(method, path) for method, path, _ in calls] != [("POST", "/v1/context-pack"), ("POST", "/v1/remember")]
            or calls[-1][2].get("write_mode") != "candidate"):
            raise RuntimeError("Candidate/context contract failed.")
        evidence = memory.read_event(candidates[0].evidence_ids[0])
        if evidence.content != "Adapter handled query: " + query:
            raise RuntimeError("Candidate provenance contract failed.")

        def state():
            return {table: [tuple(row) for row in memory.store.connection.execute("SELECT * FROM " + table)]
                    for table in ("claims", "candidate_claims", "evidence_events", "candidate_evidence_links")}

        before = state()
        for current_token, current_namespace in ((read_only, namespace), (allowed, "certification/foreign")):
            try:
                run_once("http://fixture.invalid", current_token, current_namespace, query)
            except AletheiaForbiddenError as exc:
                if exc.code != "forbidden" or exc.status_code != 403:
                    raise RuntimeError("Incorrect error envelope.") from exc
            else:
                raise RuntimeError("Adapter hid a required permission error.")
            if state() != before:
                raise RuntimeError("Denied adapter operation changed memory.")
        return {"context_read": True, "candidate_writes": 1, "active_writes": 0,
                "denied_write_preserved_state": True, "foreign_namespace_denied": True,
                "private_context_excluded": True, "transport": "in_process_service"}
