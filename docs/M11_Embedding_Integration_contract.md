
M11 — Real Embeddings + Vector Store

Recommended milestone name

M11 — Production Semantic Retrieval

Fuller name:

M11 — Real Embeddings, Vector Indexing, and Semantic Retrieval Governance

Purpose

M11 should replace the current mock-only semantic layer with a real, configurable semantic retrieval stack while preserving Aletheia’s local-first, privacy-aware, provenance-preserving behavior.

The goal is not merely:

Add embeddings.

The real goal is:

Add governed semantic recall that can be trusted operationally.

Why M11 comes first

Real embeddings are infrastructure. LLM extraction will benefit from better semantic retrieval later, but it should not depend on a half-finished vector layer.

M11 gives Aletheia:

- production semantic search
- query expansion substrate
- clustering substrate
- duplicate detection improvement
- reflection/source discovery improvement
- better context-pack recall

without yet introducing the heavier risks of LLM-generated memory.

⸻

M11 core scope

I would include exactly what you listed, with a few additions.

1. Keep MockEmbeddingProvider

This is non-negotiable.

MockEmbeddingProvider stays forever for deterministic tests.

It should remain the default for:

unit tests
conformance tests
offline examples
CI
golden retrieval tests

Do not let real model nondeterminism infect core tests.

2. Add real embedding provider abstraction

Aletheia already has plugin protocols for embedding providers and vector indexes, which makes this milestone natural rather than bolted-on.  

Provider types should be:

mock
local_http
ollama_style
openai_compatible
plugin

I would define the interface around capabilities, not vendor names.

Example:

class EmbeddingProvider:
    name: str
    provider_type: str
    model: str
    dimension: int
    def embed_texts(
        self,
        texts: list[str],
        *,
        namespace: str,
        privacy_level: str,
        purpose: str,
        metadata: dict | None = None,
    ) -> list[list[float]]:
        ...

The provider should return metadata:

EmbeddingResult(
    vector=[...],
    model="...",
    dimension=1536,
    provider="...",
    content_hash="...",
    token_count=None,
    created_at=...
)

3. Add vector-store abstraction

Start with embedded/local-first.

Recommended order:

1. SQLite vector blob store + brute-force/small ANN adapter
2. Local file-backed vector index
3. Plugin-backed vector index
4. External vector stores later

Do not jump directly to Qdrant/pgvector/LanceDB as required dependencies.

Aletheia’s strength is local-first simplicity. External vector stores should be optional.

Suggested interface:

class VectorStore:
    name: str
    supports_namespace_filter: bool
    supports_metadata_filter: bool
    supports_delete: bool
    def upsert(self, records: list[VectorRecord]) -> None:
        ...
    def search(
        self,
        *,
        namespace: str,
        query_vector: list[float],
        limit: int,
        filters: dict | None = None,
    ) -> list[VectorSearchResult]:
        ...
    def delete(self, target_ids: list[str], *, namespace: str) -> None:
        ...
    def stats(self, namespace: str | None = None) -> dict:
        ...

4. Track index lineage carefully

Every embedding record needs enough metadata to answer:

Which model produced this?
Which provider produced this?
What dimension was used?
What content was embedded?
Was it redacted?
Was it chunked?
Which namespace?
Which privacy level?
Which index version?
Which source object?
Is it stale?

Minimum metadata:

embedding_id
namespace
target_id
target_type
provider
provider_version
model
dimension
content_hash
input_hash
privacy_level
index_version
chunk_id
chunk_text_hash
created_at
stale_reason

5. Add semantic index versioning

This is important.

If the provider/model/dimension changes, Aletheia must know old vectors are stale.

Example index version identity:

semantic_index_version =
  hash(provider + model + dimension + chunking_policy + redaction_policy)

When this changes:

old vectors remain but are marked stale
new index run begins
retrieval can choose latest valid index
reindex can resume

6. Add reindex/resume behavior

Required operations:

aletheia index semantic status
aletheia index semantic run
aletheia index semantic resume
aletheia index semantic verify
aletheia index semantic mark-stale
aletheia index semantic prune-stale

Python API:

memory.index_semantic(
    namespace="user/default",
    target_type="claims",
    provider="local",
    model="...",
    force=False,
    resume=True,
)

M11 should support:

incremental indexing
resume after crash
skip unchanged content by hash
mark stale on provider/model change
delete vectors after redaction/forget
protected-mode redaction
index verification

7. Protected-mode semantic safety

This is the most important governance requirement.

Protected mode must prevent:

secret evidence text -> plaintext embedding input logs
secret evidence text -> external embedding provider
secret evidence text -> plaintext semantic index metadata
secret evidence text -> recoverable vector store payload

Default policy:

public/personal: index normally
sensitive: index only redacted or local-only, depending policy
secret: do not index by default

M11 should add semantic indexing policies:

no_sensitive_indexing
index_redacted_sensitive
local_only_sensitive
explicit_sensitive_indexing

The default should be:

no_sensitive_indexing

or:

index_public_and_personal_only

This matches Aletheia’s existing protected-mode doctrine.

⸻

M11 acceptance tests

M11 should pass tests like:

test_mock_provider_stays_deterministic
test_local_embedding_provider_records_model_dimension
test_embedding_records_content_hash
test_vector_store_upsert_search_delete
test_hybrid_retrieval_uses_real_vectors
test_provider_dimension_change_marks_old_index_stale
test_reindex_resume_skips_completed_items
test_redaction_deletes_or_stales_vectors
test_secret_content_not_sent_to_external_provider
test_protected_mode_blocks_secret_semantic_indexing
test_vector_results_still_respect_claim_status_conflict_scope_privacy

That last one is critical:

Vector search may improve recall, but it must never bypass governance.
