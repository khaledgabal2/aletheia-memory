"""Negotiated candidate review: SQLite atomicity, opaque revisions and safe replay."""
from dataclasses import asdict
from datetime import timedelta
import hashlib
import hmac
import json
import re
import secrets
import sqlite3

from cryptography.fernet import Fernet, InvalidToken

from aletheia.core.ids import new_id
from aletheia.core.time import parse_iso, utc_now, utc_now_iso
from aletheia.service.errors import ServiceError, idempotency_conflict, validation_error
from aletheia.service.reads import ReadAccess


REVIEW_PROFILE = "memory-review-v1"
MUTATION = re.compile(r"^/v1/candidates/([^/]+)/(promote|reject)$")
DETAIL = re.compile(r"^/v1/candidates/([^/]+)$")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


class ReviewProtocol:
    def __init__(self, service):
        self.service = service
        self.memory = service.memory
        self.db = self.memory.store.connection
        self.generation = None
        self.secret = secrets.token_bytes(32)
        self.cipher = Fernet(Fernet.generate_key())

    def state(self):
        row = self.db.execute("SELECT generation, epoch FROM review_state WHERE id=1").fetchone()
        if row is None:
            raise ServiceError("stale_schema", "Review state is unavailable; inspect the migration.", status_code=503)
        if self.generation is not None and self.generation != row[0]:
            self.service.service_identity = new_id("service")
            self.secret = secrets.token_bytes(32)
            self.cipher = Fernet(Fernet.generate_key())
        self.generation = row[0]
        return tuple(row)

    @staticmethod
    def handles(method, endpoint, contract):
        return bool(method == "POST" and MUTATION.fullmatch(endpoint) or
                    method == "GET" and contract is not None and (endpoint == "/v1/candidates" or DETAIL.fullmatch(endpoint)))

    @staticmethod
    def scope(context):
        return hashlib.sha256(canonical({"credential": context.token_id, "client": context.client_id,
            "capabilities": sorted(context.capabilities), "grants": sorted(context.namespace_grants),
            "privacy": context.privacy_ceiling, "expires": context.token.expires_at if context.token else None}).encode()).hexdigest()

    def revision(self, candidate_id, context, state):
        message = canonical([self.service.service_identity, state, candidate_id, self.scope(context)])
        return "rev_" + hmac.new(self.secret, message.encode(), hashlib.sha256).hexdigest()

    def process(self, *, method, endpoint, query, payload, headers, request_id, request_hash):
        contract = self.service._header(headers, "X-Aletheia-Contract")
        if contract is not None and contract != REVIEW_PROFILE:
            raise ServiceError("unsupported_contract", "This candidate operation requires memory-review-v1 or legacy mode.", status_code=409)
        try:
            with self.memory.store.transaction(immediate=method == "POST"):
                # Authenticate again after acquiring the SQLite lock/snapshot.
                context = self.service._authenticate(method, endpoint, headers)
                self.service.auth.require_capability(context, "memory:review")
                state = self.state()
                access = ReadAccess(self.service, context)
                if method == "GET":
                    if endpoint == "/v1/candidates":
                        data, pagination = self.list(query, context, access, state)
                    else:
                        target = DETAIL.fullmatch(endpoint).group(1)
                        access.require("candidate_claim", target)
                        data = self.detail(target, context, state)
                        pagination = None
                    return 200, self.service._success(data=data, warnings=[], pagination=pagination, request_id=request_id)
                target, action = MUTATION.fullmatch(endpoint).groups()
                access.require("candidate_claim", target)
                candidate = self.memory.read_candidate(target)
                guarded = contract == REVIEW_PROFILE or "expected_revision" in payload
                if not guarded:
                    return self.legacy_mutation(candidate, action, payload, context, access, endpoint, headers, request_id, request_hash)
                return self.mutate(candidate, action, payload, context, access, state, endpoint, headers, request_id)
        except sqlite3.OperationalError as error:
            if getattr(error, "sqlite_errorcode", 0) & 255 in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}:
                raise ServiceError("database_busy", "Review could not acquire a consistent write transaction; retry with the same operation key.", status_code=503) from None
            raise

    def detail(self, candidate_id, context, state):
        return {**asdict(self.memory.read_candidate(candidate_id)), "revision": self.revision(candidate_id, context, state)}

    def list(self, query, context, access, state):
        if set(query) - {"namespace", "status", "memory_type", "project_id", "limit", "cursor"} or any(len(values) != 1 for values in query.values()):
            raise validation_error("Unknown or repeated review-list parameter.")
        filters = {name: query.get(name, [None])[0] for name in ("namespace", "status", "memory_type", "project_id")}
        if not filters["namespace"]:
            raise validation_error("Review listing requires an explicit namespace.")
        self.service.auth.require_namespace(context, namespace=filters["namespace"], project_id=filters["project_id"])
        value = query.get("limit", ["50"])[0]
        if len(value) > 8 or not value.isascii() or not value.isdecimal() or not 1 <= int(value) <= 200:
            raise validation_error("Review limit must be an integer from 1 to 200.")
        limit = int(value)
        binding = {"filters": filters, "limit": limit, "scope": self.scope(context), "state": list(state), "service": self.service.service_identity}
        after = None
        if query.get("cursor"):
            token = query["cursor"][0]
            try:
                if len(token) > 8192:
                    raise ValueError("cursor size")
                decoded = json.loads(self.cipher.decrypt(token.encode(), ttl=900))
                if decoded["binding"] != binding:
                    raise ServiceError("stale_cursor", "The review list changed; restart from its first page.", status_code=409)
                after = decoded["after"]
                if not isinstance(after, list) or len(after) != 2 or not all(isinstance(item, str) for item in after):
                    raise ValueError("cursor shape")
            except (InvalidToken, ValueError, KeyError, TypeError):
                raise ServiceError("invalid_cursor", "The review cursor is invalid or expired; restart the list.", status_code=400) from None
        visible = []
        scanned = 0
        while len(visible) <= limit:
            clauses, params = ["cc.namespace=?"], [filters["namespace"]]
            for field, column in [("status", "candidate_status"), ("memory_type", "memory_type")]:
                if filters[field] is not None:
                    clauses.append(f"cc.{column}=?")
                    params.append(filters[field])
            if filters["project_id"] is not None:
                clauses.append("EXISTS (SELECT 1 FROM extraction_runs er JOIN ingestion_batches ib ON ib.id=er.batch_id WHERE er.id=cc.extraction_run_id AND ib.project_id=?)")
                params.append(filters["project_id"])
            if after:
                clauses.append("(cc.created_at<? OR (cc.created_at=? AND cc.id>?))")
                params.extend([after[0], after[0], after[1]])
            rows = self.db.execute("SELECT cc.id, cc.created_at FROM candidate_claims cc WHERE " + " AND ".join(clauses) + " ORDER BY cc.created_at DESC, cc.id ASC LIMIT 200", params).fetchall()
            if not rows:
                break
            for row in rows:
                scanned += 1
                if scanned > 10000:
                    raise ServiceError("review_scan_limit", "Narrow review filters before listing this dataset.", status_code=503)
                after = [row["created_at"], row["id"]]
                if access.allowed("candidate_claim", row["id"]):
                    visible.append(self.detail(row["id"], context, state))
                    if len(visible) > limit:
                        break
            if len(rows) < 200:
                break
        next_cursor = None
        if len(visible) > limit:
            last = visible[limit - 1]
            next_cursor = self.cipher.encrypt(canonical({"binding": binding, "after": [last["created_at"], last["id"]]}).encode()).decode()
        return visible[:limit], {"limit": limit, "count": min(len(visible), limit), "next_cursor": next_cursor}

    def mutate(self, candidate, action, payload, context, access, state, endpoint, headers, request_id):
        if "expected_revision" not in payload:
            raise ServiceError("precondition_required", "Inspect the candidate and submit its expected_revision.", status_code=428)
        if set(payload) - {"reason", "expected_revision"}:
            raise validation_error("Review mutations accept only reason and expected_revision; no force or implicit edits.")
        revision, reason = payload["expected_revision"], payload.get("reason")
        if not isinstance(revision, str) or not 1 <= len(revision) <= 256:
            raise validation_error("expected_revision must be a nonempty opaque string.")
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 4096:
            raise validation_error("A nonempty review reason of at most 4096 characters is required.")
        key = self.service._header(headers, "Idempotency-Key")
        if not key or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,200}", key):
            raise validation_error("Supply an Idempotency-Key of 1-200 ASCII letters, digits, dots, underscores, colons or hyphens.")
        credential = context.token_id
        if credential is None:
            raise ServiceError("unauthorized", "Negotiated review requires an authenticated credential.", status_code=401)
        record_id = hashlib.sha256(canonical([credential, key]).encode()).hexdigest()
        fingerprint = hashlib.sha256(canonical(["POST", endpoint, candidate.namespace, payload]).encode()).hexdigest()
        row = self.db.execute("SELECT * FROM review_replays WHERE id=?", (record_id,)).fetchone()
        if row is not None and parse_iso(row["expires_at"]) <= utc_now():
            self.db.execute("DELETE FROM review_replays WHERE id=?", (record_id,))
            row = None
        if row is not None:
            if row["request_hash"] != fingerprint:
                raise idempotency_conflict("Idempotency key reused with another review operation or payload.")
            outcome = json.loads(row["response_json"])
            if outcome["claim_id"]:
                access.require("claim", outcome["claim_id"])
            return 200, self.service._success(data=outcome, request_id=request_id, warnings=[], pagination=None)
        # Replay precedes stale comparison: the successful write advances state.
        if not hmac.compare_digest(revision.encode(), self.revision(candidate.id, context, state).encode()):
            raise ServiceError("stale_revision", "Memory changed after inspection. Refresh and request a new explicit decision.", status_code=412)
        if candidate.candidate_status in {"promoted", "rejected", "duplicate", "invalid"}:
            raise ServiceError("review_conflict", "The candidate is no longer awaiting this review decision.", status_code=409)
        operation_id, audit_id, applied_at = new_id("rop"), new_id("aud"), utc_now_iso()
        reviewer = "credential:" + credential
        if action == "promote":
            claim = self.memory.promote_candidate(candidate.id, reason=reason, reviewer=reviewer)
            claim_id = claim.id
            decision_id = self.db.execute("SELECT id FROM extraction_decisions WHERE candidate_id=? AND decision='promote' ORDER BY rowid DESC LIMIT 1", (candidate.id,)).fetchone()[0]
        else:
            claim_id = None
            decision_id = self.memory.reject_candidate(candidate.id, reason=reason, reviewer=reviewer).id
        outcome = {"operation_id": operation_id, "audit_id": audit_id, "candidate_id": candidate.id,
                   "action": action, "claim_id": claim_id, "decision_id": decision_id,
                   "reviewed_revision": revision, "result_revision": self.revision(candidate.id, context, self.state()), "applied_at": applied_at}
        self.db.execute("INSERT INTO audit_log (id, namespace, target_type, target_id, action, details, created_at) VALUES (?, ?, 'candidate_claim', ?, 'candidate.review_applied', ?, ?)",
            (audit_id, candidate.namespace, candidate.id, canonical({"operation_id": operation_id, "decision_id": decision_id, "action": action}), applied_at))
        self.db.execute("INSERT INTO review_replays (id, credential_id, method, endpoint, namespace, request_hash, operation_id, response_json, created_at, expires_at) VALUES (?, ?, 'POST', ?, ?, ?, ?, ?, ?, ?)",
            (record_id, credential, endpoint, candidate.namespace, fingerprint, operation_id, canonical(outcome), applied_at, (utc_now() + timedelta(hours=24)).isoformat()))
        return 200, self.service._success(data=outcome, request_id=request_id, warnings=[], pagination=None)

    def legacy_mutation(self, candidate, action, payload, context, access, endpoint, headers, request_id, request_hash):
        options = dict(method="POST", endpoint=endpoint, headers=headers, payload=payload,
                       request_hash=request_hash, namespace=candidate.namespace,
                       client_id="credential:" + context.token_id if context.token_id else "tokenless")
        replay = self.service._idempotency_replay(**options)
        if replay is not None:
            if action == "promote":
                access.require("claim", replay["data"]["id"])
                if asdict(self.memory.read_claim(replay["data"]["id"])) != replay["data"]:
                    raise ServiceError("replay_result_changed", "The legacy result changed; inspect current memory before continuing.", status_code=409)
            return int(replay.pop("_status_code", 200)), replay
        reason = self.service._required(payload, "reason")
        result = self.memory.promote_candidate(candidate.id, reason=reason) if action == "promote" else self.memory.reject_candidate(candidate.id, reason=reason)
        response = self.service._success(data=asdict(result), warnings=[], pagination=None, request_id=request_id)
        self.service._idempotency_store(**options, status_code=200, response=response)
        return 200, response
