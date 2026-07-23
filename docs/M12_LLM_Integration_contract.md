M12 — Governed LLM Extraction

Recommended milestone name

M12 — Governed LLM Memory Formation

Fuller name:

M12 — Governed LLM Extraction, Suggestion, Summarization, and Reflection Support

Purpose

M12 should implement configurable LLM providers for memory-related tasks while preserving the core Aletheia rule:

LLM output is never truth by default.

LLMs may produce:

candidate memories
candidate inferences
entity suggestions
category suggestions
summary drafts
reflection drafts
query expansions
conflict explanations

They must not produce:

trusted facts
active claims
core memories
unreviewed policies
unreviewed procedures
silent deletions

The current docs state that LLMExtractor is a placeholder and that the repository currently has rule-based and mock extraction only. M12 is the right milestone to turn that placeholder into a real governed implementation.  

⸻

M12 core scope

1. Provider abstraction

Provider types:

mock_llm
local_http
ollama_style
openai_compatible
plugin

Again, keep provider names abstract where possible.

Interface:

class LLMProvider:
    name: str
    provider_type: str
    model: str
    def complete_json(
        self,
        *,
        messages: list[dict],
        schema: dict,
        temperature: float,
        max_tokens: int | None,
        metadata: dict | None = None,
    ) -> dict:
        ...

I would require structured output for all memory-writing tasks.

No free-form memory mutation.

2. Implement LLMExtractor

The extractor should take evidence and produce:

CandidateClaimDraft[]

Not claims.

class LLMExtractor:
    def extract(
        self,
        *,
        namespace: str,
        evidence: list[EvidenceEvent],
        policy: ExtractionPolicy,
    ) -> list[CandidateClaimDraft]:
        ...

Each candidate must include:

subject
predicate
object
memory_type
evidence_span
suggested_confidence
suggested_scope
privacy_level
candidate_reason
extraction_prompt_id
model
provider
temperature
schema_version

3. Add prompt/config provenance

Every LLM run should be auditable.

New records:

llm_runs
llm_prompts
llm_prompt_versions
llm_outputs
llm_safety_flags

Minimum fields:

llm_run_id
provider
model
prompt_template_id
prompt_version
temperature
schema_version
input_evidence_ids
input_hash
output_hash
created_at
status
warnings

Do not store full prompt/output by default if it may contain sensitive content. Use protected-mode policy.

4. Add leak checks

Before sending content to an LLM provider, Aletheia should classify:

provider locality
network access
privacy level
protected mode
user permission
namespace policy

Default rules:

public/personal -> allowed if provider policy allows
sensitive -> local-only unless explicit approval
secret -> blocked by default

Provider policy should declare:

external_network_access: true/false
stores_data: true/false/unknown
supports_no_log_mode: true/false/unknown

Aletheia should not send secret evidence to an external provider by accident.

5. Add LLM task types

M12 should not be only extraction.

It should support governed LLM tasks:

extract_candidates
suggest_entities
suggest_categories
expand_query
summarize_evidence
draft_reflection
explain_conflict
suggest_scope
suggest_duplicate_merge

But all outputs should remain:

suggestions
drafts
candidates
review tasks

not canonical memory.

6. Add query expansion carefully

LLM query expansion is useful but risky.

For retrieval:

expanded = memory.expand_query(
    namespace="user/default",
    query="what should I know before writing M12?",
    provider="local_llm",
)

Return:

original query
expanded terms
entities
categories
likely memory types
excluded assumptions

Do not let query expansion inject facts into the context pack.

7. Add summarization without loss

LLM summaries must use Aletheia’s existing abstraction discipline.

A summary should be:

summary draft
reflection candidate
abstraction candidate

with backlinks to evidence and claims.

Never:

summary replaces evidence

8. Add review gates

LLM outputs should enter one of these states:

pending_review
validated
promoted
rejected
needs_scope
needs_conflict_resolution
unsafe
invalid_schema
insufficient_evidence

Promotion must pass M2/M3/M4 gates:

evidence gate
schema gate
privacy gate
confidence gate
conflict gate
scope gate
derivation gate
audit gate

⸻

M12 acceptance tests

M12 should pass tests like:

test_llm_extractor_outputs_candidates_only
test_llm_output_requires_evidence_span
test_llm_output_records_provider_model_prompt_version
test_llm_output_invalid_schema_rejected
test_llm_candidate_cannot_be_active_without_review
test_external_llm_blocked_for_secret_evidence_by_default
test_sensitive_evidence_requires_explicit_policy
test_query_expansion_does_not_create_memory
test_summary_preserves_source_backlinks
test_reflection_draft_requires_review
test_llm_conflict_explanation_does_not_resolve_conflict_automatically