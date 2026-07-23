"""Semantic provider and vector-store primitives.

M11 keeps the deterministic mock provider for tests while adding governed
provider metadata, configurable HTTP providers, index versioning, and a local
SQLite vector store abstraction.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol


class EmbeddingProvider(Protocol):
    name: str
    provider_type: str
    model: str
    dimension: int
    provider_version: str
    external_network_access: bool
    stores_data: str
    supports_no_log_mode: str

    def embed_texts(
        self,
        texts: list[str],
        *,
        namespace: str | None = None,
        privacy_level: str = "personal",
        purpose: str = "semantic_index",
        metadata: dict[str, Any] | None = None,
    ) -> list[list[float]]:
        ...


class SemanticIndex(Protocol):
    provider: EmbeddingProvider

    def index_texts(
        self,
        *,
        namespace: str,
        target_type: str,
        items: list[tuple[str, str]],
    ) -> int:
        ...


@dataclass(frozen=True)
class EmbeddingResult:
    vector: list[float]
    provider: str
    provider_type: str
    provider_version: str
    model: str
    dimension: int
    content_hash: str
    input_hash: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VectorRecord:
    id: str
    namespace: str
    target_id: str
    target_type: str
    vector: list[float]
    provider: str
    model: str
    dimension: int
    content_hash: str
    input_hash: str
    privacy_level: str
    index_version: str
    created_at: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VectorSearchResult:
    target_id: str
    score: float
    vector_id: str
    metadata: dict[str, Any] = field(default_factory=dict)


class MockEmbeddingProvider:
    """Small deterministic embedding provider for local tests and demos."""

    name = "mock"
    provider_type = "mock"
    model = "mock-semantic-v1"
    dimension = 48
    provider_version = "m11"
    external_network_access = False
    stores_data = "false"
    supports_no_log_mode = "true"

    def embed_texts(
        self,
        texts: list[str],
        *,
        namespace: str | None = None,
        privacy_level: str = "personal",
        purpose: str = "semantic_index",
        metadata: dict[str, Any] | None = None,
    ) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for token in _semantic_tokens(text):
            index = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16) % self.dimension
            vector[index] += 1.0
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


class LocalHashEmbeddingProvider(MockEmbeddingProvider):
    """Local deterministic provider with configurable dimensions.

    This is intentionally not used for golden tests; it is a local-safe provider
    for demos and protected-mode environments where external embedding calls are
    not allowed.
    """

    name = "local_hash"
    provider_type = "local"
    model = "local-hash-semantic-v1"
    provider_version = "m11"

    def __init__(self, *, dimension: int | None = None):
        if dimension is not None:
            if dimension < 8:
                raise ValueError("Embedding dimension must be at least 8.")
            self.dimension = dimension


class HTTPEmbeddingProvider:
    """Configurable local/OpenAI-compatible embedding provider."""

    provider_version = "m11"
    external_network_access = True
    stores_data = "unknown"
    supports_no_log_mode = "unknown"

    def __init__(
        self,
        *,
        name: str,
        provider_type: str,
        endpoint: str,
        model: str,
        dimension: int,
        api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        if not endpoint:
            raise ValueError(f"{name} embedding provider requires an endpoint.")
        if not model:
            raise ValueError(f"{name} embedding provider requires a model.")
        if dimension <= 0:
            raise ValueError(f"{name} embedding provider requires a positive dimension.")
        self.name = name
        self.provider_type = provider_type
        self.endpoint = endpoint
        self.model = model
        self.dimension = dimension
        self.api_key = api_key
        self.timeout = timeout

    def embed_texts(
        self,
        texts: list[str],
        *,
        namespace: str | None = None,
        privacy_level: str = "personal",
        purpose: str = "semantic_index",
        metadata: dict[str, Any] | None = None,
    ) -> list[list[float]]:
        payload = {
            "model": self.model,
            "input": texts,
            "metadata": {
                "namespace": namespace,
                "privacy_level": privacy_level,
                "purpose": purpose,
                **(metadata or {}),
            },
        }
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise ValueError(f"Embedding provider {self.name!r} failed: {exc}") from exc
        vectors = self._extract_vectors(body)
        for vector in vectors:
            if len(vector) != self.dimension:
                raise ValueError(
                    f"Embedding provider {self.name!r} returned dimension {len(vector)}, "
                    f"expected {self.dimension}."
                )
        return vectors

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _extract_vectors(self, body: dict[str, Any]) -> list[list[float]]:
        if "data" in body and isinstance(body["data"], list):
            return [[float(value) for value in item["embedding"]] for item in body["data"]]
        if "embeddings" in body and isinstance(body["embeddings"], list):
            return [[float(value) for value in vector] for vector in body["embeddings"]]
        if "embedding" in body and isinstance(body["embedding"], list):
            return [[float(value) for value in body["embedding"]]]
        raise ValueError(f"Embedding provider {self.name!r} returned an unsupported payload.")


class SQLiteVectorStore:
    """Local embedded vector store backed by the existing embeddings table."""

    name = "sqlite_local"
    supports_namespace_filter = True
    supports_metadata_filter = True
    supports_delete = True

    def __init__(self, connection) -> None:
        self.connection = connection

    def upsert(self, records: list[VectorRecord]) -> None:
        for record in records:
            updated = self.connection.execute(
                """
                UPDATE embeddings
                SET
                    id = ?,
                    dimension = ?,
                    vector_ref = NULL,
                    vector_blob = ?,
                    content_hash = ?,
                    created_at = ?,
                    metadata_json = ?,
                    provider_type = ?,
                    provider_version = ?,
                    input_hash = ?,
                    privacy_level = ?,
                    index_version = ?,
                    chunk_id = ?,
                    chunk_text_hash = ?,
                    vector_store = ?,
                    vector_id = ?,
                    status = 'indexed',
                    stale_reason = NULL
                WHERE namespace = ?
                  AND target_type = ?
                  AND target_id = ?
                  AND provider = ?
                  AND model = ?
                  AND COALESCE(index_version, '') = COALESCE(?, '')
                """,
                (
                    record.id,
                    record.dimension,
                    encode_vector(record.vector),
                    record.content_hash,
                    record.created_at,
                    json.dumps(record.metadata, sort_keys=True),
                    record.metadata.get("provider_type", "unknown"),
                    record.metadata.get("provider_version", "unknown"),
                    record.input_hash,
                    record.privacy_level,
                    record.index_version,
                    record.metadata.get("chunk_id", "default"),
                    record.metadata.get("chunk_text_hash", record.content_hash),
                    self.name,
                    record.id,
                    record.namespace,
                    record.target_type,
                    record.target_id,
                    record.provider,
                    record.model,
                    record.index_version,
                ),
            )
            if updated.rowcount:
                continue
            self.connection.execute(
                """
                INSERT INTO embeddings (
                    id, namespace, target_id, target_type, provider, model,
                    dimension, vector_ref, vector_blob, content_hash,
                    created_at, metadata_json, provider_type, provider_version,
                    input_hash, privacy_level, index_version, chunk_id,
                    chunk_text_hash, vector_store, vector_id, status, stale_reason
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'indexed', NULL)
                """,
                (
                    record.id,
                    record.namespace,
                    record.target_id,
                    record.target_type,
                    record.provider,
                    record.model,
                    record.dimension,
                    encode_vector(record.vector),
                    record.content_hash,
                    record.created_at,
                    json.dumps(record.metadata, sort_keys=True),
                    record.metadata.get("provider_type", "unknown"),
                    record.metadata.get("provider_version", "unknown"),
                    record.input_hash,
                    record.privacy_level,
                    record.index_version,
                    record.metadata.get("chunk_id", "default"),
                    record.metadata.get("chunk_text_hash", record.content_hash),
                    self.name,
                    record.id,
                ),
            )

    def search(
        self,
        *,
        namespace: str,
        query_vector: list[float],
        target_type: str,
        provider: str,
        model: str,
        index_version: str | None = None,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        params: list[Any] = [namespace, target_type, provider, model]
        clauses = [
            "namespace = ?",
            "target_type = ?",
            "provider = ?",
            "model = ?",
            "COALESCE(status, 'indexed') = 'indexed'",
            "vector_blob IS NOT NULL",
        ]
        if index_version:
            clauses.append("index_version = ?")
            params.append(index_version)
        filters = filters or {}
        for field in ("privacy_level", "target_id"):
            if field in filters:
                clauses.append(f"{field} = ?")
                params.append(filters[field])
        target_ids = filters.get("target_ids")
        if target_ids is not None:
            if isinstance(target_ids, str):
                target_ids = [target_ids]
            else:
                target_ids = list(target_ids)
            if not target_ids:
                return []
            clauses.append(f"target_id IN ({','.join('?' for _ in target_ids)})")
            params.extend(target_ids)
        rows = self.connection.execute(
            f"""
            SELECT id, target_id, vector_blob, metadata_json
            FROM embeddings
            WHERE {' AND '.join(clauses)}
            """,
            params,
        ).fetchall()
        results: list[VectorSearchResult] = []
        for row in rows:
            vector = decode_vector(row["vector_blob"])
            score = cosine_similarity(query_vector, vector)
            if score <= 0:
                continue
            results.append(
                VectorSearchResult(
                    target_id=row["target_id"],
                    score=score,
                    vector_id=row["id"],
                    metadata=_json(row["metadata_json"], {}),
                )
            )
        results.sort(key=lambda result: (-result.score, result.target_id))
        return results[:limit]

    def delete(self, target_ids: list[str], *, namespace: str) -> None:
        if not target_ids:
            return
        self.connection.execute(
            f"""
            DELETE FROM embeddings
            WHERE namespace = ? AND target_id IN ({','.join('?' for _ in target_ids)})
            """,
            [namespace, *target_ids],
        )

    def stats(self, namespace: str | None = None) -> dict[str, Any]:
        params: list[Any] = []
        where = ""
        if namespace:
            where = "WHERE namespace = ?"
            params.append(namespace)
        rows = self.connection.execute(
            f"""
            SELECT provider, model, COALESCE(status, 'indexed') AS status, count(*) AS count
            FROM embeddings
            {where}
            GROUP BY provider, model, COALESCE(status, 'indexed')
            ORDER BY provider, model, status
            """,
            params,
        ).fetchall()
        return {"name": self.name, "records": [dict(row) for row in rows]}


def provider_for_name(name: str | None, *, model: str | None = None, dimension: int | None = None) -> EmbeddingProvider:
    if name in {None, "mock"}:
        return MockEmbeddingProvider()
    if name in {"local", "local_hash"}:
        return LocalHashEmbeddingProvider(dimension=dimension)
    if name in {"local_http", "ollama_style", "openai_compatible"}:
        prefix = "ALETHEIA_EMBEDDING"
        env_prefix = f"{prefix}_{name.upper()}"
        endpoint = (
            os.environ.get(f"{env_prefix}_ENDPOINT")
            or os.environ.get(f"{prefix}_ENDPOINT")
            or ""
        )
        resolved_model = model or os.environ.get(f"{env_prefix}_MODEL") or os.environ.get(f"{prefix}_MODEL") or ""
        resolved_dimension = dimension or int(
            os.environ.get(f"{env_prefix}_DIMENSION")
            or os.environ.get(f"{prefix}_DIMENSION")
            or "0"
        )
        api_key = os.environ.get(f"{env_prefix}_API_KEY") or os.environ.get(f"{prefix}_API_KEY")
        timeout = float(os.environ.get(f"{env_prefix}_TIMEOUT") or os.environ.get(f"{prefix}_TIMEOUT") or "30")
        return HTTPEmbeddingProvider(
            name=name,
            provider_type=name,
            endpoint=endpoint,
            model=resolved_model,
            dimension=resolved_dimension,
            api_key=api_key,
            timeout=timeout,
        )
    raise ValueError(f"Unknown embedding provider: {name}")


def embed_texts_with_metadata(
    provider: EmbeddingProvider,
    texts: list[str],
    *,
    namespace: str,
    privacy_level: str,
    purpose: str,
    metadata: dict[str, Any] | None = None,
) -> list[EmbeddingResult]:
    vectors = provider.embed_texts(
        texts,
        namespace=namespace,
        privacy_level=privacy_level,
        purpose=purpose,
        metadata=metadata,
    )
    results: list[EmbeddingResult] = []
    for text, vector in zip(texts, vectors, strict=True):
        if len(vector) != provider.dimension:
            raise ValueError(
                f"Embedding provider {provider.name!r} returned dimension {len(vector)}, "
                f"expected {provider.dimension}."
            )
        digest = text_hash(text)
        results.append(
            EmbeddingResult(
                vector=vector,
                provider=provider.name,
                provider_type=getattr(provider, "provider_type", "unknown"),
                provider_version=getattr(provider, "provider_version", "unknown"),
                model=provider.model,
                dimension=provider.dimension,
                content_hash=digest,
                input_hash=digest,
                metadata=metadata or {},
            )
        )
    return results


def semantic_index_version(
    *,
    provider: EmbeddingProvider,
    chunking_policy: str = "whole-target-v1",
    redaction_policy: str = "index_public_and_personal_only",
) -> str:
    raw = "|".join(
        [
            provider.name,
            getattr(provider, "provider_type", "unknown"),
            provider.model,
            str(provider.dimension),
            chunking_policy,
            redaction_policy,
        ]
    )
    return "siv_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def encode_vector(vector: list[float]) -> bytes:
    return json.dumps(vector, separators=(",", ":")).encode("utf-8")


def decode_vector(blob: bytes | memoryview) -> list[float]:
    raw = bytes(blob).decode("utf-8")
    return [float(value) for value in json.loads(raw)]


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return max(0.0, min(numerator / (left_norm * right_norm), 1.0))


def _json(value: str | None, default):
    if value is None:
        return default
    return json.loads(value)


def _semantic_tokens(text: str) -> list[str]:
    raw_tokens = re.findall(r"[A-Za-z0-9_]+", text.lower())
    tokens: list[str] = []
    for token in raw_tokens:
        tokens.append(_normalize_token(token))
    return tokens


def _normalize_token(token: str) -> str:
    synonyms = {
        "detail": "detail",
        "detailed": "detail",
        "details": "detail",
        "comprehensive": "detail",
        "thorough": "detail",
        "architecture": "architecture",
        "architectural": "architecture",
        "design": "architecture",
        "contract": "contract",
        "contracts": "contract",
        "spec": "contract",
        "specification": "contract",
        "explanation": "explain",
        "explanations": "explain",
        "answers": "answer",
        "responses": "answer",
        "progress": "progress",
        "status": "progress",
        "concise": "concise",
        "brief": "concise",
        "short": "concise",
        "ingestion": "ingestion",
        "ingest": "ingestion",
        "semantic": "semantic",
        "recall": "retrieval",
        "retrieval": "retrieval",
    }
    return synonyms.get(token, token)
