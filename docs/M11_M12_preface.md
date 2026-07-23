Embeddings may improve recall. LLMs may propose meaning. Neither may bypass truth governance.


M11 = make semantic retrieval real, governed, reindexable, and production-safe.
M12 = make LLM-powered memory formation real, governed, reviewable, and non-authoritative.

In other words:

M11 improves recall.
M12 improves memory formation.

That distinction matters.

Why the split is right

M11 has infrastructure risk

M11 risks:

wrong dimensions
stale embeddings
reindex failures
privacy leakage through vectors
external store inconsistency
protected-mode violations
semantic search bypassing filters

These are engineering and data-governance risks.

M12 has epistemic risk

M12 risks:

hallucinated memories
unsupported extraction
overconfident summaries
prompt injection
privacy leaks to model provider
LLM-generated false inferences
implicit promotion of suggestions

These are truth and governance risks.

Mixing them would make debugging painful.

If retrieval gets worse after adding both at once, you will not know whether the cause is:

bad embeddings
bad vector ranking
bad LLM extraction
bad query expansion
bad summaries
bad promotion gates

Splitting makes the test boundary clean.

⸻

Suggested sequencing inside each milestone

M11 internal order

1. Formalize embedding provider interface.
2. Keep mock provider as default test provider.
3. Add local configurable provider.
4. Add embedding metadata/versioning.
5. Add vector store abstraction.
6. Add local embedded vector store.
7. Integrate with hybrid retrieval.
8. Add reindex/resume.
9. Add protected-mode semantic policies.
10. Add semantic conformance/scorecard.

M12 internal order

1. Formalize LLM provider interface.
2. Add mock deterministic LLM provider for tests.
3. Implement LLMExtractor using structured output.
4. Add LLM run/prompt provenance tables.
5. Add leak checks and provider policies.
6. Add candidate extraction.
7. Add entity/category suggestions.
8. Add query expansion.
9. Add summarization/reflection drafts.
10. Add governed review and conformance scorecard.

⸻

Additional recommendation: add M11/M12 as experimental first

Because Aletheia has stable v1 surfaces now, M11 and M12 should be introduced as:

M11: semantic-retrieval-beta
M12: llm-governance-beta

They can be additive minor releases:

M11 -> v1.2.0
M12 -> v1.3.0

or, if you want faster iteration:

M11 -> v1.2.0
M12 -> v1.2.x experimental feature flag

But I prefer separate minor releases:

v1.2.0 = real semantic retrieval
v1.3.0 = governed LLM extraction

That keeps release notes clean.

⸻

Feature flags

I would gate them explicitly:

[semantic]
enabled = true
provider = "mock"
vector_store = "sqlite_local"
protected_mode_policy = "index_public_and_personal_only"
[llm]
enabled = false
provider = "mock"
external_allowed = false
require_review = true
store_prompts = "metadata_only"

Default should be conservative:

semantic enabled with mock/local-safe provider
LLM disabled unless configured
external providers disabled unless explicitly configured

⸻

The strategic position

This is the right evolution after M10.

Aletheia has already built:

memory governance
platform stability
federation boundaries

Now the weak point is obvious:

semantic recall is still mock-grade
LLM extraction is still placeholder-grade

So M11 and M12 are not scope creep. They strengthen the original core.

They bring Aletheia back to the heart of the project:

better remembering
better recalling
better memory formation

while preserving everything that makes Aletheia different:

provenance
candidate-first writes
confidence decay
conflict handling
protected mode
audit
review
local-first control

My final recommendation

Proceed exactly with your split.

I would write the contracts as:

M11 — Production Semantic Retrieval
M12 — Governed LLM Memory Formation

And I would explicitly make this the doctrine:

Embeddings may improve recall. LLMs may propose meaning. Neither may bypass truth governance.

That sentence should sit at the top of both contracts.