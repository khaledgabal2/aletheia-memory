
# **Production Design: Local AI Agent Memory Library**
## **1. Core thesis**

A production-grade memory library must **not** be “a vector database plus summaries.” That fails in practice. It becomes stale, self-contradictory, un-auditable, and too eager to believe its own compressions.

The correct design is a **local, auditable, multi-layer memory operating system** for agents:

**Raw evidence is immutable. Canonical memories are curated. Inferences are labeled. Confidence decays by volatility. Retrieval is contextual, not just semantic.**

This design borrows the strongest current patterns from agent memory systems: short-term versus long-term memory across sessions, semantic/episodic/procedural memory separation, memory blocks, hot-path and background memory writing, and OS-style memory hierarchy. LangGraph describes short-term memory as thread-scoped and long-term memory as cross-session namespaced storage; it also separates semantic, episodic, and procedural memory types.   LlamaIndex uses short-term memory that flushes into long-term memory blocks such as fact extraction and vector memory blocks.   MemGPT/Letta popularized the OS analogy: core in-context memory plus external archival and recall memory, with agents moving information between tiers.   Generative Agents showed the value of storing experiences, retrieving relevant memories, and synthesizing higher-level reflections over time.  

I’ll call the library **Aletheia Memory** for this design.

---

# **2. Non-negotiable design principles**

## **Principle 1: Never trust a memory without provenance**

Every memory must answer:

- Where did this come from?
- Who or what asserted it?
- When was it observed?
- Was it directly observed, inferred, summarized, imported, or user-confirmed?
- What evidence supports it?
- What evidence contradicts it?

A memory without provenance should be treated as a note, not a fact.

## **Principle 2: Separate evidence from belief**

The library stores two different things:

|**Layer**|**Meaning**|
|---|---|
|**Evidence**|Raw messages, tool outputs, files, observations, transcripts, user corrections, logs|
|**Claims**|Structured candidate facts extracted from evidence|
|**Canonical memories**|Curated claims the system is allowed to use|
|**Inferences**|Derived conclusions, always labeled as inferred|
|**Reflections**|Abstractions over many memories|
|**Procedures**|Learned behaviors, preferences, policies, skills|

This prevents the agent from confusing “someone said X” with “X is true.”

## **Principle 3: Abstraction without loss requires retaining the source**

True abstraction without information loss is impossible if the original is discarded. So the design does **lossless abstraction by indirection**:

Summaries and abstractions are allowed, but every abstraction must point back to the exact source evidence and lower-level memories that produced it.

The agent can use the abstraction for speed, but the system can always reopen the evidence when accuracy matters.

## **Principle 4: Contradiction is a first-class object**

Contradictions should not be silently overwritten. They should be represented explicitly:

- active claim
- superseded claim
- disputed claim
- time-scoped claim
- context-scoped claim
- false claim
- unresolved conflict

The agent should normally retrieve the active claim, but the audit trail stays intact.

## **Principle 5: Confidence is dynamic**

A memory’s confidence is not a single permanent number. It changes with:

- source reliability
- number of independent confirmations
- age
- volatility of the fact
- contradiction pressure
- user correction
- successful use
- failed use
- re-verification

A user’s current project goal may decay quickly. Their name should decay slowly. A temporary preference like “today I want short answers” should decay very quickly.

---

# **3. High-level architecture**

```text
Local Agent
   |
   |  read-before-reasoning
   v
Memory Context Builder
   |
   +--> Working Memory / Session State
   +--> Core Memory Blocks
   +--> Retrieval Engine
            |
            +--> Lexical Index
            +--> Vector Index
            +--> Entity / Graph Index
            +--> Temporal Index
            +--> Claim Store
            +--> Procedure Store
            +--> Evidence Store
   |
   v
Agent Reasoning / Tool Use
   |
   |  write-after-acting
   v
Memory Write Pipeline
   |
   +--> Event Capture
   +--> Segmentation
   +--> Claim Extraction
   +--> Entity Resolution
   +--> Categorization
   +--> Contradiction Detection
   +--> Confidence Scoring
   +--> Promotion / Curation
   +--> Index Update
   |
   v
Background Memory Workers
   |
   +--> Consolidation
   +--> Reflection
   +--> Decay
   +--> Re-verification
   +--> Conflict Resolution
   +--> Procedure Optimization
   +--> Garbage Collection / Archival
```

The library should run in three modes:

|**Mode**|**Use case**|
|---|---|
|**Embedded**|Single local agent imports the library directly|
|**Sidecar daemon**|Any local agent talks to `memoryd` over HTTP/gRPC/Unix socket|
|**Shared local service**|Multiple agents share memory with namespaces, permissions, and audit logs|

For “any local AI agent,” the sidecar daemon is the cleanest default. It avoids binding the design to one framework.

---

# **4. Memory types**

The library should support at least these memory classes.

|**Type**|**Example**|**Storage style**|**Decay behavior**|
|---|---|---|---|
|**Working memory**|Current task state|In-process / session DB|Very short|
|**Episodic memory**|“On June 12 the agent failed because it used the wrong file.”|Event log + vector index|Medium|
|**Semantic memory**|“Example User is a chief geophysicist.”|Claim store + graph|Slow, unless user profile changes|
|**Procedural memory**|“When explaining technical matters, be practical and direct.”|Policy/procedure store|Slow, revised by feedback|
|**Preference memory**|“User prefers concise status updates.”|Profile + claim store|Medium|
|**Project memory**|“Current project is memory library design.”|Project namespace|Medium/fast|
|**Skill memory**|“For seismic inversion reviews, first check acquisition geometry.”|Procedure graph|Slow|
|**Negative memory**|“Do not use deprecated workflow X.”|Constraint store|Medium/slow|
|**Conflict memory**|“Two different addresses are recorded.”|Conflict graph|No decay until resolved|
|**Inference memory**|“Likely works in upstream O&G because of role and documents.”|Inference store|Faster unless confirmed|

LangMem and LangGraph both use the semantic/episodic/procedural distinction for agent memory; LangMem also distinguishes collections from profiles, where profiles are better for current state and collections are better when recall across many interactions matters.  

---

# **5. Storage design**

## **5.1 Core stores**

A production implementation should not put everything in one vector DB. Use separate stores with one transactionally consistent metadata layer.

|**Store**|**Purpose**|
|---|---|
|**Event ledger**|Append-only raw evidence|
|**Claim store**|Structured atomic assertions|
|**Entity registry**|People, projects, tools, files, concepts|
|**Graph store**|Relationships and logical links|
|**Vector index**|Semantic similarity retrieval|
|**Lexical index**|Exact names, rare terms, IDs, code symbols|
|**Temporal index**|Time-scoped facts and session history|
|**Procedure store**|Learned instructions and policies|
|**Conflict store**|Contradiction clusters and resolution state|
|**Audit log**|Every mutation, promotion, demotion, deletion|
|**Feedback store**|Success/failure/user correction signals|

For a local-first default, I would use:

|**Component**|**Default**|
|---|---|
|Metadata and claims|SQLite or Postgres|
|Full-text search|SQLite FTS5, Tantivy, or Postgres text search|
|Vector search|Qdrant, LanceDB, Chroma, or pgvector|
|Graph|SQLite tables initially; optional Neo4j/Kùzu for larger deployments|
|Files/evidence blobs|Local encrypted object store|
|Queue|SQLite-backed durable queue or NATS for larger systems|

SQLite FTS5 provides full-text search for large document collections, and Qdrant supports vector search plus payload indexes for filtering structured metadata.   These are examples, not hard dependencies.

---

# **6. Data model**

## **6.1 Evidence event**

```json
{
  "event_id": "evt_...",
  "tenant_id": "local_user",
  "agent_id": "agent_research_01",
  "session_id": "sess_...",
  "source_type": "user_message | assistant_message | tool_output | file | api | system",
  "source_uri": "optional file path, message id, tool call id",
  "content_hash": "sha256...",
  "content": "raw text or pointer to encrypted blob",
  "created_at": "2026-06-30T10:15:00-05:00",
  "observed_at": "2026-06-30T10:15:00-05:00",
  "trust_level": "user_confirmed | tool_verified | model_generated | imported | unknown",
  "privacy_level": "public | personal | sensitive | secret",
  "retention_policy": "default | ephemeral | permanent | delete_on_session_end"
}
```

Evidence is append-only unless the user explicitly deletes it. Even then, the system should keep a tombstone so derived memories can be invalidated.

## **6.2 Atomic claim**

```json
{
  "claim_id": "clm_...",
  "subject": {
    "entity_id": "ent_user_default",
    "text": "Example User"
  },
  "predicate": "has_role",
  "object": {
    "value": "Chief Geophysicist",
    "type": "string"
  },
  "qualifiers": {
    "scope": "user_profile",
    "time_valid_from": null,
    "time_valid_to": null,
    "location": null,
    "condition": null
  },
  "memory_type": "semantic",
  "abstraction_level": 0,
  "evidence_ids": ["evt_..."],
  "derived_from_claims": [],
  "status": "candidate | active | superseded | disputed | rejected | archived",
  "confidence_base": 0.86,
  "confidence_effective": 0.82,
  "half_life_days": 365,
  "importance": 0.78,
  "volatility": "low | medium | high",
  "source_reliability": 0.9,
  "created_at": "2026-06-30T10:15:00-05:00",
  "last_accessed_at": null,
  "last_verified_at": null,
  "contradicts": [],
  "supersedes": [],
  "promoted_to_core": false
}
```

## **6.3 Reflection / abstraction**

```json
{
  "reflection_id": "ref_...",
  "title": "User communication preference",
  "summary": "The user values practical, direct, intellectually serious responses.",
  "abstraction_level": 2,
  "source_claims": ["clm_1", "clm_2", "clm_3"],
  "source_events": ["evt_1", "evt_2"],
  "information_loss_policy": "lossless_via_backlinks",
  "status": "active",
  "confidence_base": 0.74,
  "half_life_days": 180
}
```

The reflection is not the source of truth. It is a compressed index over source truth.

---

# **7. Write pipeline**

## **7.1 Capture**

Every interaction produces immutable events:

- user message
- assistant response
- tool call
- tool result
- file read
- code execution
- user correction
- explicit memory instruction
- task outcome

The write path should be idempotent using `event_id` and `content_hash`.

## **7.2 Segment**

Break events into semantic chunks:

- sentences
- tool result records
- file sections
- action/outcome pairs
- user preference statements
- project facts
- corrections
- instructions
- decisions

Each segment keeps offsets into the original evidence.

## **7.3 Extract candidate memories**

A local model or rule extractor emits candidate memories:

```json
{
  "candidate": "User prefers direct, practical responses.",
  "type": "preference",
  "subject": "user",
  "predicate": "prefers_response_style",
  "object": "direct and practical",
  "evidence": "message span 14:29-14:73",
  "confidence": 0.78,
  "should_store": true,
  "reason": "Stable user instruction"
}
```

Candidate extraction should use a strict schema. Do not let the model write arbitrary prose directly into the permanent memory store.

## **7.4 Classify memory type**

The classifier assigns:

- semantic
- episodic
- procedural
- preference
- project
- skill
- negative
- conflict
- inference

## **7.5 Normalize**

Normalization includes:

- entity resolution
- predicate normalization
- time extraction
- scope detection
- unit conversion
- synonym mapping
- ontology tagging
- privacy tagging

Example:

```text
“Example User is the chief geophysicist”
```

becomes:

```text
subject: ent_user_default
predicate: has_role
object: Chief Geophysicist
scope: user_profile
type: semantic
```

## **7.6 Contradiction check**

Before promotion, the candidate is compared against active claims with the same or related subject/predicate.

Contradiction detectors:

1. **Exact structured conflict**Example: `preferred_name = Example User` versus `preferred_name = Mike`.
2. **Temporal conflict**  
    Example: “lives in Houston” and “lives in Denver” may not conflict if dates differ.
3. **Logical conflict**Example: `is_deleted(file_X)=true` conflicts with `file_X is active`.
4. **Semantic/NLI conflict**  
    Example: “prefers concise answers” conflicts with “prefers very detailed answers,” depending on scope.
5. **User correction conflict**  
    User corrections override model-generated memory unless there is strong contrary evidence.

## **7.7 Score**

Initial confidence should combine:

```text
C_base =
  source_reliability
  × extraction_confidence
  × evidence_specificity
  × schema_validity
  × confirmation_strength
  × contradiction_penalty
```

Then the runtime confidence applies decay and re-verification.

## **7.8 Promote or quarantine**

Candidate memories go to one of five states:

|**State**|**Meaning**|
|---|---|
|**Rejected**|Noise, unsafe, too vague, or unsupported|
|**Candidate**|Stored but not normally retrieved|
|**Active**|Usable by retrieval|
|**Core**|Always or frequently placed in context|
|**Disputed**|Requires resolution or user confirmation|

Promotion should be conservative. False memories are worse than missing memories.

---

# **8. Read pipeline**

The agent should use a **read-before-reasoning** pattern:

1. Receive task/user message.
2. Build retrieval query plan.
3. Search multiple indexes.
4. Fuse results.
5. Resolve conflicts.
6. Compress into a context pack.
7. Send the context pack to the agent.

LangGraph’s docs describe short-term state read at the start of a step, and long-term memory saved across namespaces for recall across sessions.  

## **8.1 Query planning**

The library should not blindly embed the user’s latest message. It should generate a retrieval plan:

```json
{
  "task": "answer_user",
  "needed_memory": [
    "user_profile",
    "current_project",
    "relevant_procedures",
    "recent_session_context",
    "known_constraints"
  ],
  "filters": {
    "tenant_id": "local_user",
    "privacy_max": "allowed_for_agent",
    "status": ["active", "core"],
    "exclude_disputed_unless_needed": true
  },
  "token_budget": 1800
}
```

## **8.2 Hybrid retrieval**

Retrieval should combine:

|**Signal**|**Purpose**|
|---|---|
|Vector similarity|Meaning|
|Lexical search|Names, IDs, exact phrases|
|Graph traversal|Relationships|
|Temporal proximity|Recent task continuity|
|Importance|High-value memories|
|Effective confidence|Avoid stale/weak memories|
|Procedural priority|Keep behavioral rules|
|Diversity|Avoid returning ten near-duplicates|
|Conflict state|Avoid unresolved false certainty|

Suggested ranking:

```text
score =
  0.25 semantic_similarity
+ 0.18 lexical_score
+ 0.15 graph_relevance
+ 0.15 effective_confidence
+ 0.10 importance
+ 0.08 recency_or_task_continuity
+ 0.05 procedural_priority
+ 0.04 user_confirmation
- 0.20 unresolved_conflict_penalty
- 0.10 redundancy_penalty
```

Weights should be tunable per agent.

## **8.3 Context pack**

The library returns a structured context pack, not raw memory dumps.

```xml
<memory_context generated_at="2026-06-30T10:30:00-05:00">
  <core_memory>
    <memory confidence="0.94" source="user_confirmed">
      User is Example User, Chief Geophysicist.
    </memory>
  </core_memory>

  <project_memory>
    <memory confidence="0.88">
      Current request: design a production-grade local AI agent memory library.
    </memory>
  </project_memory>

  <procedural_memory>
    <memory confidence="0.82">
      User prefers practical, direct, intellectually serious responses.
    </memory>
  </procedural_memory>

  <warnings>
    <warning>
      Do not treat inferred memories as facts unless confirmed.
    </warning>
  </warnings>
</memory_context>
```

The context pack should include confidence labels when useful, but not overload the model with metadata every time.

---

# **9. Confidence half-life decay**

## **9.1 Separate truth confidence from retrieval salience**

This matters.

A memory can be true but no longer useful. Another can be useful but uncertain.

So track two dynamic scores:

|**Score**|**Meaning**|
|---|---|
|**Truth confidence**|How likely the claim is true|
|**Retrieval salience**|How useful it is right now|

Do not decay universal truths aggressively. Do decay volatile personal/project/task memories.

## **9.2 Decay formula**

For a claim:

```text
age_days = now - last_verified_at_or_created_at

decay_factor = 2 ^ (-age_days / half_life_days)

confidence_effective =
  clamp(
    confidence_base
    × decay_factor
    × source_reliability_multiplier
    × confirmation_multiplier
    × contradiction_multiplier
    × verification_multiplier,
    0,
    1
  )
```

## **9.3 Volatility-based half-life**

|**Memory kind**|**Suggested half-life**|
|---|---|
|Current task state|1–7 days|
|Temporary preference|7–30 days|
|Project status|14–90 days|
|User preference|90–365 days|
|User identity/profile|365–2000 days|
|Domain knowledge|1000+ days|
|Tool/API behavior|30–180 days|
|Procedural skill|180–1000 days|
|Explicit user correction|Long, often 1000+ days|
|Inference-only memory|7–90 days|

## **9.4 Reinforcement**

Reinforcement should be careful.

Good reinforcement:

- user confirms it
- tool verifies it
- repeated independent evidence supports it
- using it improved task outcome

Bad reinforcement:

- the agent simply retrieved it many times
- the model repeated it
- the memory appears in its own summaries

Self-repetition is not evidence.

---

# **10. Contradiction removal and truth maintenance**

The design should not literally “remove contradiction” by deleting everything inconsistent. It should **resolve, scope, supersede, or quarantine** contradictions.

## **10.1 Conflict family**

When a contradiction is detected, create a conflict family:

```json
{
  "conflict_id": "conf_...",
  "subject": "ent_user",
  "predicate": "preferred_response_length",
  "claims": ["clm_short", "clm_detailed"],
  "status": "resolved | unresolved | time_scoped | context_scoped",
  "resolution_policy": "latest_user_confirmed_wins",
  "active_claim": "clm_short",
  "notes": "Detailed answers preferred for technical design; concise updates preferred during long tasks."
}
```

## **10.2 Resolution policies**

|**Conflict type**|**Policy**|
|---|---|
|User correction vs model memory|User correction wins|
|Newer user profile vs older user profile|Newer wins, older superseded|
|Tool-verified fact vs model inference|Tool-verified wins|
|Two user statements|Scope by time/context; ask only when necessary|
|Preference conflict|Allow conditional preferences|
|Factual conflict with no reliable source|Mark disputed|
|Inference conflict with fact|Fact wins|
|Procedure conflict|Run evaluation or require approval|

## **10.3 Temporal scoping**

Many “contradictions” are not contradictions. They are time changes.

```text
User lives in Calgary.       valid: 2023-01-01 to 2025-03-15
User lives in Houston.       valid: 2025-03-16 to present
```

The current answer should use Houston. The historical answer may still need Calgary.

## **10.4 Context scoping**

Preferences can differ by context.

```text
For quick operational questions: concise.
For philosophical or design questions: detailed, rigorous, poetic when appropriate.
For code diffs: minimal commentary.
```

This is better than overwriting one preference with another.

---

# **11. Curation and promotion**

Memory should have a lifecycle.

```text
Observed
  -> Candidate
  -> Active
  -> Promoted
  -> Core
  -> Reflected
  -> Archived / Superseded / Rejected
```

## **11.1 Promotion criteria**

A memory can be promoted when it has:

- clear evidence
- stable meaning
- useful future value
- no unresolved contradiction
- good confidence
- appropriate privacy classification
- known scope
- known half-life
- successful prior retrieval or explicit user confirmation

## **11.2 Core memory**

Core memory is small and high-value. It is the memory equivalent of L1 cache.

Core memory may include:

- user identity
- stable user preferences
- agent persona/role
- safety boundaries
- current long-running projects
- persistent instructions
- high-priority facts

Letta describes memory blocks that agents or specialized memory agents can update over time, while external databases support retrieval through vector or graph storage.   LlamaIndex similarly uses memory blocks with priorities so some blocks are retained before lower-priority blocks when token budgets are tight.  

## **11.3 Curation agents**

Use specialized local workers:

|**Worker**|**Role**|
|---|---|
|**Extractor**|Turns events into candidate memories|
|**Curator**|Decides what deserves active memory|
|**Contradiction Resolver**|Groups and resolves conflicts|
|**Reflector**|Builds higher-level abstractions|
|**Verifier**|Rechecks volatile memories|
|**Procedure Optimizer**|Updates behavioral rules from feedback|
|**Garbage Collector**|Archives low-value memories|
|**Privacy Auditor**|Detects sensitive data and enforces retention|

These workers may use LLMs, but the final write must go through deterministic validators.

---

# **12. Abstraction without information loss**

Use a **memory pyramid**:

```text
Level 0: Raw evidence
Level 1: Atomic claims
Level 2: Cluster summaries
Level 3: Reflections / patterns
Level 4: Procedures / policies
Level 5: Core identity and durable operating principles
```

Rules:

1. Higher levels never replace lower levels.
2. Every abstraction stores backlinks.
3. Every summary must declare what it omits.
4. Any high-stakes use can expand the abstraction back to evidence.
5. If source evidence is deleted, derived abstractions are invalidated or re-derived.
6. Summaries should be versioned, not overwritten.

Example:

```text
Raw evidence:
  User repeatedly asks for direct, practical answers.
  User asks for philosophical depth in some contexts.
  User dislikes vague answers.

Atomic claims:
  prefers_practical_answers = true
  prefers_philosophical_depth = context-dependent
  dislikes_vagueness = true

Reflection:
  User wants practical clarity, but appreciates depth when the topic is conceptual.

Procedure:
  Be direct first. Add depth when the subject is design, philosophy, learning, or conceptual understanding.
```

That final procedure is useful, but it should never erase the underlying nuance.

---

# **13. Logical, semantic, and factual inference**

These three must be separate. Mixing them is how memory systems start hallucinating.

## **13.1 Logical inference**

Logical inference uses explicit rules over structured claims.

Example rules:

```text
IF user_has_role(Chief Geophysicist)
AND topic(seismic_interpretation)
THEN retrieve_domain_context(geophysics)

IF claim_A supersedes claim_B
THEN claim_B is not current

IF preference applies_to(context)
THEN include_in_context_pack
```

Use cases:

- hierarchy reasoning
- access control
- temporal validity
- contradiction propagation
- project dependency reasoning
- “if X is deleted, all derived memories from X are invalid”

Implementation options:

- Datalog-like rule engine
- RDF-style triples
- SQL recursive queries
- lightweight Prolog engine
- graph traversal plus constraints

Logical inference can be high confidence if its premises are high confidence and the rule is deterministic.

## **13.2 Semantic inference**

Semantic inference uses meaning similarity, clustering, and latent relationships.

Examples:

- “rock physics,” “seismic inversion,” and “geophysical interpretation” are related.
- A user asking many reservoir characterization questions suggests a relevant domain cluster.
- Two memories may be duplicates even with different wording.

Semantic inference is excellent for retrieval and categorization, but it should not automatically become factual truth.

Correct handling:

```text
semantic_related(memory_A, memory_B) = true
confidence = 0.72
status = retrieval_hint
not a factual claim
```

## **13.3 Factual inference**

Factual inference derives a new claim from evidence.

Example:

```text
Evidence:
  “I’m flying to Oslo on Thursday for the SEG workshop.”

Candidate factual inferences:
  user_has_travel_plan(destination=Oslo)
  event_related_to(user, SEG workshop)
  likely_unavailable_during_travel = maybe
```

The first two are close factual inferences. The third is speculative and should be labeled as such.

Factual inference rules:

|**Inference type**|**Storage status**|
|---|---|
|Direct extraction|Candidate or active|
|Entailed by reliable evidence|Active if confidence high|
|Probable but not entailed|Inference-only|
|Speculative|Retrieval hint only|
|Model guess|Do not store unless useful and labeled|

---

# **14. Self-learning and self-improvement**

The library should improve without secretly rewriting reality.

## **14.1 Learning loops**

|**Loop**|**What improves**|
|---|---|
|User corrections|Fact quality|
|Task outcomes|Retrieval ranking|
|Explicit feedback|Procedures and style|
|Repeated usage|Salience, not truth|
|Conflict resolution|Claim accuracy|
|Reflection|Abstraction quality|
|Evaluation tests|Memory policies|
|Re-verification|Staleness control|

## **14.2 What the system may self-modify**

Allowed:

- retrieval weights
- memory promotion thresholds
- half-life defaults
- summarization policies
- procedural instructions
- category ontology additions
- duplicate detection thresholds
- query planning templates

Not allowed without explicit admin approval:

- deletion of high-confidence evidence
- disabling audit logs
- weakening privacy rules
- modifying safety policies
- silently changing user-confirmed facts
- training/fine-tuning on private data for external use

## **14.3 Procedural learning**

Procedure memories are the safest place for self-improvement.

Example:

```text
Observation:
  User rejected a generic design answer.

Updated procedure:
  For architecture/design requests, provide implementation-level modules,
  data model, lifecycle, and failure modes.
```

LangMem’s procedural memory model treats agent behavior as instructions that evolve through feedback and experience, including prompt optimization from trajectories.  

## **14.4 Evaluation gate**

Before promoting a new procedure:

1. Compare old and new procedure.
2. Run against local regression examples.
3. Check for safety/privacy regressions.
4. Store diff.
5. Promote only if better.
6. Roll back if future outcomes degrade.

---

# **15. Indexing and categorization**

## **15.1 Index every memory multiple ways**

Each memory should be indexed by:

- embedding vector
- lexical terms
- entities
- predicates
- categories
- source
- time
- confidence
- privacy level
- namespace
- project
- memory type
- abstraction level
- conflict status

## **15.2 Category ontology**

Start with a universal base ontology:

```text
identity
preference
project
task
relationship
domain_knowledge
tool_usage
file_knowledge
decision
mistake
success_pattern
constraint
procedure
safety
privacy
schedule
location
communication_style
negative_memory
```

Then allow domain plugins:

```text
geophysics:
  seismic_processing
  inversion
  interpretation
  acquisition
  rock_physics
  reservoir_characterization
  velocity_model
  uncertainty
```

## **15.3 Auto-categorization**

Auto-categorization should emit multiple labels with confidence:

```json
{
  "labels": [
    {"name": "preference.communication_style", "confidence": 0.87},
    {"name": "procedure.response_generation", "confidence": 0.66}
  ]
}
```

Low-confidence labels are search hints, not canonical categories.

---

# **16. Persistence across sessions**

The library should support persistent context at four levels:

|**Level**|**Persistence**|
|---|---|
|Session|Current conversation/thread|
|Project|Across sessions for one project|
|Agent|Across all sessions for one agent|
|User/org|Shared across agents with permission|

## **16.1 Namespaces**

Use hierarchical namespaces:

```text
/user/{user_id}
/user/{user_id}/profile
/user/{user_id}/projects/{project_id}
/agent/{agent_id}/procedures
/org/{org_id}/shared
/files/{file_id}
/sessions/{session_id}
```

LangGraph uses custom namespaces for long-term memory organization, often including user or organization IDs.  

## **16.2 Context continuity**

At session start:

1. Load core memory.
2. Load active project memory if project is known.
3. Retrieve recent relevant sessions.
4. Retrieve user preferences.
5. Retrieve applicable procedures.
6. Check unresolved conflicts.
7. Build initial context pack.

At session end:

1. Summarize session.
2. Extract candidate memories.
3. Update project state.
4. Store task outcomes.
5. Queue background curation.

---

# **17. API design**

## **17.1 Minimal API**

```python
memory.write(events, namespace, policy=None)

memory.retrieve(
    query,
    namespace,
    filters=None,
    token_budget=2000,
    include_evidence=False
)

memory.context_pack(
    task,
    user_id,
    agent_id,
    session_id,
    token_budget=2000
)

memory.resolve_claim(
    subject,
    predicate,
    scope=None,
    include_conflicts=False
)

memory.feedback(
    memory_id,
    signal="useful | wrong | stale | confirmed | contradicted",
    evidence=None
)

memory.promote(memory_id, level="active | core")
memory.demote(memory_id, reason)
memory.forget(selector, mode="redact | tombstone | hard_delete")
memory.audit(memory_id)
```

## **17.2 Agent tool interface**

Expose as tools any agent can call:

```json
[
  {
    "name": "memory_search",
    "description": "Search long-term memory with filters."
  },
  {
    "name": "memory_remember",
    "description": "Store a candidate memory with evidence."
  },
  {
    "name": "memory_resolve",
    "description": "Resolve the current best claim about an entity."
  },
  {
    "name": "memory_feedback",
    "description": "Mark a memory useful, wrong, stale, or confirmed."
  }
]
```

The agent may suggest memories, but the library decides what becomes canonical.

---

# **18. Security, privacy, and local control**

A local memory library should assume memory is sensitive.

Minimum requirements:

- encryption at rest
- per-agent permissions
- per-namespace access control
- audit logs
- user-visible memory browser
- explicit deletion controls
- import/export
- source-level redaction
- derived-memory invalidation after deletion
- prompt-injection filtering on imported content
- no external telemetry by default
- no cloud calls unless explicitly configured

Privacy labels should propagate. If evidence is marked `secret`, derived claims cannot become low-privacy memories.

---

# **19. Failure modes and mitigations**

|**Failure mode**|**Mitigation**|
|---|---|
|False memory|Evidence requirement, user correction priority, confidence scoring|
|Stale memory|Half-life decay, re-verification, temporal scoping|
|Contradictory memory|Conflict families, active/superseded states|
|Over-summarization|Lossless backlinks to raw evidence|
|Vector-only retrieval failure|Hybrid lexical/vector/graph retrieval|
|Self-reinforcing hallucination|Do not treat model repetition as evidence|
|Privacy leak|Namespaces, ACL, privacy propagation|
|Context bloat|Context packer, priority, abstraction levels|
|User preference overfitting|Scope preferences by context|
|Silent corruption|Append-only ledger, audit log, snapshots|
|Catastrophic deletion|Tombstones, backups, derived invalidation|
|Bad procedural self-update|Evaluation gate and rollback|

---

# **20. Requirement mapping**

|**User requirement**|**Design feature**|
|---|---|
|**1. Self-learning and self-improving over time**|Feedback loops, procedural learning, curation workers, evaluation gates|
|**2. Indexing and categorization**|Hybrid indexes, ontology, labels, entity graph, namespaces|
|**3. Removal of contradiction**|Conflict families, supersession, dispute states, truth maintenance|
|**4. Curation and promotion**|Candidate → active → core lifecycle, promotion thresholds, curator worker|
|**5. Abstraction without loss of information**|Memory pyramid with immutable evidence and backlinks|
|**6. Confidence half-life decay**|Volatility-based decay formula, truth confidence vs salience|
|**7. Context persists across sessions**|Durable namespaces, session/project/user/agent memory scopes|
|**8. Logical inference**|Rule engine over claims, graph, constraints, temporal logic|
|**9. Semantic inference**|Embeddings, clustering, duplicate detection, semantic retrieval hints|
|**10. Factual inference**|Evidence-grounded claim extraction, entailment labels, provenance|

---

# **21. Recommended production implementation**

## **21.1 Default local stack**

```text
memoryd
  Language: Rust or Python
  API: HTTP + gRPC + Unix socket
  SDKs: Python, TypeScript
  DB: SQLite for embedded, Postgres for heavier deployment
  Vector: Qdrant or LanceDB
  Full text: SQLite FTS5 or Tantivy
  Embeddings: local embedding model
  LLM extraction: pluggable local model
  Queue: SQLite durable jobs
  Config: YAML/TOML
  Encryption: age/libsodium
```

## **21.2 Package layout**

```text
aletheia-memory/
  memoryd/
  sdk/python/
  sdk/typescript/
  crates/
    evidence-ledger/
    claim-store/
    retrieval/
    inference/
    curation/
    decay/
    security/
  plugins/
    qdrant/
    sqlite/
    postgres/
    local-llm/
    openai-compatible/
  cli/
  dashboard/
  migrations/
  evals/
```

## **21.3 Runtime services**

```text
memoryd serve
memoryd import ./chat_logs
memoryd search "what does the user prefer?"
memoryd audit clm_123
memoryd conflicts list
memoryd decay run
memoryd curate run
memoryd export --namespace user/default
```

---

# **22. The key hard rule**

The strongest production design is not the one that remembers the most. It is the one that remembers **with discipline**.

A good memory library should be able to say:

```text
I know this.
I think this.
I inferred this.
This used to be true.
This is disputed.
This is stale.
This came from here.
This should not be used anymore.
```

That is the difference between a toy memory layer and a real production memory system.