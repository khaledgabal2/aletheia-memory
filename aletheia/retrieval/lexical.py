"""SQLite FTS retrieval and deterministic M1 ranking."""

from __future__ import annotations

import math
import re
import sqlite3
from datetime import UTC, datetime

from aletheia.core.time import parse_iso, utc_now
from aletheia.models.retrieval import RetrievalResult

EXCLUDED_ALWAYS = ("rejected",)
EXCLUDED_DEFAULT = ("archived", "superseded", "disputed")

MEMORY_TYPE_PRIORITY = {
    "procedure": 0.95,
    "preference": 0.90,
    "project": 0.85,
    "project_state": 0.85,
    "identity": 0.85,
    "decision": 0.80,
    "correction": 0.80,
    "fact": 0.70,
    "session_summary": 0.65,
    "episodic": 0.55,
    "inference": 0.40,
}

STATUS_PRIORITY = {
    "core": 1.00,
    "active": 0.80,
    "candidate": 0.30,
    "disputed": 0.10,
    "archived": 0.05,
    "superseded": 0.00,
}


def tokenize(text: str) -> list[str]:
    return [term.lower() for term in re.findall(r"[A-Za-z0-9_]+", text)]


def fts_query(text: str) -> str:
    terms = tokenize(text)
    return " OR ".join(terms)


def claim_text(subject: str, predicate: str, object: str) -> str:
    pretty_subject = subject[:1].upper() + subject[1:]
    pretty_predicate = predicate.replace("_", " ")
    return f"{pretty_subject} {pretty_predicate} {object}."


def lexical_score(query: str, fields: list[str]) -> float:
    query_terms = set(tokenize(query))
    if not query_terms:
        return 0.0
    haystack = " ".join(fields).lower()
    matched = sum(1 for term in query_terms if term in haystack)
    return matched / len(query_terms)


def recency_score(created_at: str) -> float:
    created = parse_iso(created_at)
    if not created:
        return 0.0
    age_days = max((utc_now() - created).total_seconds() / 86400.0, 0.0)
    return 1 / (1 + age_days / 30)


def staleness_penalty(created_at: str, last_verified_at: str | None, half_life_days: float) -> float:
    start = parse_iso(last_verified_at) or parse_iso(created_at)
    if not start or half_life_days <= 0:
        return 0.0
    age_days = max((utc_now() - start).total_seconds() / 86400.0, 0.0)
    if age_days <= half_life_days:
        return 0.0
    return min((age_days - half_life_days) / half_life_days, 1.0)


def deterministic_score(
    *,
    lexical: float,
    confidence_effective: float,
    memory_type: str,
    status: str,
    project_relevance: float,
    created_at: str,
    importance: float,
    conflict_ids: list[str],
    last_verified_at: str | None,
    half_life_days: float,
) -> float:
    conflict_penalty = 1.0 if conflict_ids and status != "active" else 0.0
    stale_penalty = staleness_penalty(created_at, last_verified_at, half_life_days)
    return (
        0.35 * lexical
        + 0.20 * confidence_effective
        + 0.15 * MEMORY_TYPE_PRIORITY.get(memory_type, 0.50)
        + 0.10 * STATUS_PRIORITY.get(status, 0.20)
        + 0.10 * project_relevance
        + 0.05 * recency_score(created_at)
        + 0.05 * importance
        - 0.20 * conflict_penalty
        - 0.10 * stale_penalty
    )


def governed_claim_filter(namespace: str, filters: dict | None = None, *, alias: str = "c") -> tuple[list[str], list[object]]:
    filters = filters or {}
    params: list[object] = [namespace, EXCLUDED_ALWAYS[0]]
    clauses = [f"{alias}.namespace = ?", f"{alias}.status NOT IN (?)"]
    statuses = _as_list(filters.get("statuses") or filters.get("status"))
    if statuses:
        clauses.append(f"{alias}.status IN ({','.join('?' for _ in statuses)})")
        params.extend(statuses)
    else:
        excluded = []
        if not filters.get("include_archived", False):
            excluded.extend(["archived", "superseded"])
        if not filters.get("include_disputed", False):
            excluded.append("disputed")
        if excluded:
            clauses.append(f"{alias}.status NOT IN ({','.join('?' for _ in excluded)})")
            params.extend(excluded)
    memory_types = _as_list(filters.get("memory_types") or filters.get("memory_type"))
    if memory_types:
        clauses.append(f"{alias}.memory_type IN ({','.join('?' for _ in memory_types)})")
        params.extend(memory_types)
    if filters.get("subject"):
        clauses.append(f"{alias}.subject = ?")
        params.append(filters["subject"])
    if filters.get("predicate"):
        clauses.append(f"{alias}.predicate = ?")
        params.append(filters["predicate"])
    if filters.get("min_confidence") is not None:
        clauses.append(f"{alias}.confidence_effective >= ?")
        params.append(float(filters["min_confidence"]))
    categories = _as_list(filters.get("categories"))
    if categories:
        clauses.append(
            f"""
            EXISTS (
                SELECT 1
                FROM memory_category_labels mcl
                WHERE mcl.namespace = {alias}.namespace
                  AND mcl.target_id = {alias}.id
                  AND mcl.target_type = 'claim'
                  AND mcl.label IN ({','.join('?' for _ in categories)})
            )
            """
        )
        params.extend(categories)
    if filters.get("project_id"):
        clauses.append(
            f"""
            (
                NOT EXISTS (
                    SELECT 1
                    FROM project_claim_links pcl_any
                    WHERE pcl_any.namespace = {alias}.namespace
                      AND pcl_any.claim_id = {alias}.id
                )
                OR EXISTS (
                    SELECT 1
                    FROM project_claim_links pcl
                    WHERE pcl.namespace = {alias}.namespace
                      AND pcl.claim_id = {alias}.id
                      AND pcl.project_id = ?
                )
            )
            """
        )
        params.append(filters["project_id"])
    if filters.get("session_id"):
        clauses.append(
            f"""
            (
                NOT EXISTS (
                    SELECT 1
                    FROM session_claim_links scl_any
                    WHERE scl_any.claim_id = {alias}.id
                )
                OR EXISTS (
                    SELECT 1
                    FROM session_claim_links scl
                    WHERE scl.claim_id = {alias}.id
                      AND scl.session_id = ?
                )
            )
            """
        )
        params.append(filters["session_id"])
    return clauses, params


class SQLiteFTSRetriever:
    """Lexical retriever that keeps the public retrieval interface stable."""

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def retrieve(
        self,
        namespace: str,
        query: str,
        filters: dict | None = None,
        limit: int = 10,
    ) -> list[RetrievalResult]:
        filters = filters or {}
        project_id = filters.get("project_id")
        limit = max(1, int(limit))
        candidate_limit = max(limit, min(max(limit * 20, 100), 1000))

        clauses, params = governed_claim_filter(namespace, filters, alias="c")
        match = fts_query(query)
        if match:
            clauses.append("claims_fts MATCH ?")
            params.append(match)

        sql = f"""
            SELECT c.*
            FROM claims_fts
            JOIN claims c ON c.id = claims_fts.claim_id
            WHERE {' AND '.join(clauses)}
            GROUP BY c.id
            ORDER BY c.created_at DESC, c.id ASC
            LIMIT ?
        """
        params.append(candidate_limit)
        rows = self.connection.execute(sql, params).fetchall()
        claim_ids = [row["id"] for row in rows]
        evidence_by_claim = self._evidence_ids_by_claim(claim_ids)
        conflict_by_claim = self._conflict_ids_by_claim(claim_ids)
        project_by_claim = self._project_ids_by_claim(claim_ids)
        results: list[RetrievalResult] = []
        for row in rows:
            evidence_ids = evidence_by_claim.get(row["id"], [])
            conflict_ids = conflict_by_claim.get(row["id"], [])
            project_ids = project_by_claim.get(row["id"], [])
            project_relevance = 1.0 if project_id and project_id in project_ids else 0.0
            lexical = lexical_score(
                query,
                [
                    row["subject"],
                    row["predicate"],
                    row["object"],
                    row["memory_type"],
                    claim_text(row["subject"], row["predicate"], row["object"]),
                ],
            )
            # Metadata-only retrieval should still rank deterministically.
            if not query.strip():
                lexical = 0.0
            score = deterministic_score(
                lexical=lexical,
                confidence_effective=row["confidence_effective"],
                memory_type=row["memory_type"],
                status=row["status"],
                project_relevance=project_relevance,
                created_at=row["created_at"],
                importance=row["importance"],
                conflict_ids=conflict_ids,
                last_verified_at=row["last_verified_at"],
                half_life_days=row["half_life_days"],
            )
            results.append(
                RetrievalResult(
                    claim_id=row["id"],
                    namespace=row["namespace"],
                    text=claim_text(row["subject"], row["predicate"], row["object"]),
                    subject=row["subject"],
                    predicate=row["predicate"],
                    object=row["object"],
                    memory_type=row["memory_type"],
                    status=row["status"],
                    score=score,
                    lexical_score=lexical,
                    confidence_base=row["confidence_base"],
                    confidence_effective=row["confidence_effective"],
                    importance=row["importance"],
                    created_at=row["created_at"],
                    last_verified_at=row["last_verified_at"],
                    evidence_ids=evidence_ids,
                    conflict_ids=conflict_ids,
                    project_ids=project_ids,
                )
            )
        results.sort(
            key=lambda result: (
                -result.score,
                -result.confidence_effective,
                result.created_at,
                result.claim_id,
            )
        )
        return results[:limit]

    def _evidence_ids_by_claim(self, claim_ids: list[str]) -> dict[str, list[str]]:
        if not claim_ids:
            return {}
        rows = self.connection.execute(
            f"""
            SELECT claim_id, evidence_id
            FROM claim_evidence_links
            WHERE claim_id IN ({','.join('?' for _ in claim_ids)})
            ORDER BY claim_id, evidence_id
            """,
            claim_ids,
        ).fetchall()
        return _group_ids(rows, "claim_id", "evidence_id")

    def _conflict_ids_by_claim(self, claim_ids: list[str]) -> dict[str, list[str]]:
        if not claim_ids:
            return {}
        placeholders = ",".join("?" for _ in claim_ids)
        rows = self.connection.execute(
            f"""
            SELECT claim_id, conflict_id
            FROM conflict_family_claims
            WHERE claim_id IN ({placeholders})
            UNION
            SELECT claim_id, conflict_id
            FROM conflict_claim_links
            WHERE claim_id IN ({placeholders})
            ORDER BY claim_id, conflict_id
            """,
            [*claim_ids, *claim_ids],
        ).fetchall()
        return _group_ids(rows, "claim_id", "conflict_id")

    def _project_ids_by_claim(self, claim_ids: list[str]) -> dict[str, list[str]]:
        if not claim_ids:
            return {}
        rows = self.connection.execute(
            f"""
            SELECT claim_id, project_id
            FROM project_claim_links
            WHERE claim_id IN ({','.join('?' for _ in claim_ids)})
            ORDER BY claim_id, project_id
            """,
            claim_ids,
        ).fetchall()
        return _group_ids(rows, "claim_id", "project_id")

    def _evidence_ids(self, claim_id: str) -> list[str]:
        rows = self.connection.execute(
            """
            SELECT evidence_id
            FROM claim_evidence_links
            WHERE claim_id = ?
            ORDER BY evidence_id
            """,
            (claim_id,),
        ).fetchall()
        return [row["evidence_id"] for row in rows]

    def _conflict_ids(self, claim_id: str) -> list[str]:
        rows = self.connection.execute(
            """
            SELECT conflict_id
            FROM conflict_claim_links
            WHERE claim_id = ?
            ORDER BY conflict_id
            """,
            (claim_id,),
        ).fetchall()
        return [row["conflict_id"] for row in rows]

    def _project_ids(self, claim_id: str) -> list[str]:
        rows = self.connection.execute(
            """
            SELECT project_id
            FROM project_claim_links
            WHERE claim_id = ?
            ORDER BY project_id
            """,
            (claim_id,),
        ).fetchall()
        return [row["project_id"] for row in rows]


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


def _group_ids(rows, key_field: str, value_field: str) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for row in rows:
        grouped.setdefault(row[key_field], []).append(row[value_field])
    return grouped
