# Aletheia Memory 1.4.0: Contract Hardening and Developer Experience

## Status and purpose

- Status: proposed release plan; implementation has not started through this document.
- Prepared: 2026-08-30.
- Reviewed baseline: Aletheia Memory 1.3.1, repository revision `1cb3e60`.
- Recommended release: `1.4.0`, provided the implementation remains backward-compatible.
- Scope: standalone Memory integration contracts and the ease-of-use recommendations from the user-provided v1.3.1 product review. Desktop is an optional downstream consumer, not a dependency.

New endpoint names, contract-profile names, and helper interfaces below are proposals, not claims that they already exist. Approving this plan does not itself authorize a release, a deployment, or changes to branch protection.

## 1. Executive recommendation

Combine contract hardening and developer onboarding into one focused **Integration and Developer Experience release**.

The release should make two promises:

1. **Developers can reach their first useful, auditable memory result in approximately five minutes without configuring a model.**
2. **Independent clients, including Desktop, can integrate with an explicit, typed, permission-aware, compatibility-tested service contract without guessing backend behavior.**

These are complementary outcomes. The onboarding example becomes an executable reference for the intended memory lifecycle; the hardened contracts make that lifecycle dependable across Python, HTTP, and Desktop consumers.

This is a substantive minor release, not merely a documentation refresh. It adds usable integration contracts, safer client workflows, and focused convenience features while preserving the existing governed memory model.

The release is not intended to implement Desktop itself, build a relay, bundle foundation models, or expand the memory ontology. It makes the existing platform easier to adopt and safe to build on.

### Recommended decisions

- Keep `aletheia-memory` model-neutral, local-first, and usable without Desktop or Relay.
- Preserve existing Python, CLI, HTTP, and SDK behavior unless a separately reviewed compatibility decision permits a change.
- Type and test the initial consumer profiles first; do not make complete coverage of all 199 OpenAPI paths a prerequisite.
- Add complete principal discovery and correct version reporting with a compatibility bridge for existing SDKs.
- Make the first Desktop slice read-only and polling-based.
- Require atomic stale-write protection before enabling Desktop review or editing workflows.
- Provide one primary zero-model onboarding journey, followed by optional semantic and LLM setup recipes.
- Improve existing initialization, examples, and diagnostics before introducing additional command families.
- Deliver through small, dependency-ordered PRs. Keep the protected `main` branch releasable.

### Non-negotiable: Memory is independent of Desktop

The dependency direction is strictly **Desktop -> Memory**, never **Memory -> Desktop**.

- Memory must install, build, run, test, and release when the Desktop repository is absent.
- Memory must remain fully usable through its standalone Python, CLI, HTTP, and MCP interfaces. A graphical interface is never required to initialize memory, configure access, review candidates, retrieve context, or administer supported operations.
- The Python distribution must not import or bundle the Desktop application, React, its native shell, or its application state. TypeScript contract checks are development tooling, not a runtime or installation requirement.
- Memory owns its data, configuration, credentials, governance, and migrations. It must not depend on Desktop-owned files, sessions, credentials, or startup routines to operate.
- Existing optional console functionality is an interface to Memory, not a prerequisite for the engine or service.
- Memory's required tests use its own headless fixtures and generic client harnesses. They must not check out, build, or launch Desktop. Generic browser-transport tests may exercise a minimal test page without any Desktop code.
- Memory's release decision depends on its own contract and quality gates, never on Desktop's implementation progress, documentation, tests, packaging, or release schedule.
- Desktop owns its end-to-end integration tests against a supported Memory release. Those tests can gate Desktop, not Memory.

Contract hardening benefits all clients: Python integrations, agent services, command-line tools, browser clients, and future applications. Desktop helps identify requirements, but those requirements must become general Memory capabilities rather than Desktop-specific backend behavior.

## 2. Current baseline and implications

The following observations are grounded in the current source and the earlier isolated contract check. They are not a full security audit or a claim that all existing functionality has been revalidated.

| Area | Observed baseline | Planning implication |
| --- | --- | --- |
| OpenAPI | 199 paths, 213 operations, two envelope schemas, and 121 unrestricted object request bodies. No documented path/query parameters or operation IDs. | Generated transport wrappers are possible, but meaningful endpoint-specific TypeScript types require contract work. |
| Versions | Package metadata declares `1.3.1`; service/OpenAPI reporting reuses the `1.3.0` database schema constant. API major is separately identified as `v1`. | Separate software, API, storage, and consumer-profile compatibility concepts. |
| Existing SDK compatibility | `AletheiaClient.check_compatibility()` compares `schema_version` with `aletheia_version`. | Correcting version fields without a transition could make old clients reject an otherwise compatible service. |
| Principal discovery | Normal bearer tokens can call `/v1/console/session` and receive capabilities and namespace grants. Identity and privacy ceiling are absent. | Complete the contract; do not describe it as entirely nonexistent. |
| Permissions | Promotion uses `memory:review`; Desktop documentation includes `memory:promote`. | Align Desktop with canonical server permissions. Do not add a new permission just to match a planning example. |
| Transport and concurrency | The HTTP handler has no `OPTIONS` implementation; no service event-stream or ETag/expected-revision contract was found. | Choose and test a browser topology, use polling initially, and add write preconditions where required. |
| Public stability | Published `/v1/*` routes are described as stable. | Consumer profiles add precise tested subsets; they do not retract existing public guarantees. |
| Onboarding foundations | `Memory.open()`, `retrieve()`, `context_pack()`, candidate extraction/review, `aletheia init`, `doctor`, and example generation already exist. | Simplify and connect existing capabilities rather than build a second implementation. |
| Write semantics | Embedded `Memory.remember()` defaults to an active claim. The HTTP SDK exposes explicit candidate and active-write helpers. | Do not silently change `Memory.remember()` or disguise trusted active writes as the normal agent path. |
| Documentation | README still describes PyPI publication as future work; some integration examples begin with hybrid retrieval or repository-development commands. | Make published-package installation and a deterministic lexical example the primary entry point. |

## 3. Release scope and product boundaries

### Included in 1.4.0

- Typed contracts and generated-client verification for the agreed first Desktop and agent-onboarding workflows.
- Accurate discovery metadata, complete current-principal information, and canonical permission requirements.
- A backward-compatible version/SDK transition.
- Browser transport support for the explicitly selected deployment arrangement.
- Stable errors, pagination, redaction, request correlation, and retry/idempotency semantics for selected operations.
- Atomic stale-write protection for the selected Desktop review operations.
- A minimal, additive convenience layer where existing interfaces demonstrably make onboarding cumbersome.
- A five-minute, model-free tutorial and runnable starter projects.
- First-run diagnostics and actionable setup errors.
- Optional, tested local embedding and LLM recipes using existing provider mechanisms.
- Compatibility, contract, packaging, and executable-documentation release gates.

### Explicitly excluded

- A complete Desktop/Web application or desktop installers.
- Secure pairing UI, a hosted relay, or automatic multi-device synchronization.
- Full typing or redesign of every administrative and federation endpoint.
- SSE/WebSocket infrastructure unless polling proves insufficient for an approved first-release requirement.
- Mandatory model downloads, default hosted-model calls, or mandatory embedding/LLM dependencies.
- Enterprise control-plane features or new large-scale vector backends.
- A general natural-language-to-memory promise without an explicitly enabled LLM.
- A broad HTTP-framework rewrite or unrelated schema refactor.

### Ownership

| Component | Responsibility |
| --- | --- |
| Aletheia Memory | Memory behavior, governance, authorization, contracts, revisions, safe convenience APIs, CLI onboarding, provider recipes, and compatibility guarantees. |
| Aletheia Desktop | UI, navigation, connection workflow, scope display, review experience, client-side state, and product-specific browser/native-shell behavior. |
| Generated TypeScript client | A reproducible consumer of Memory's published profile schemas; its generation and runtime conformance are tested against Memory. |
| Future Aletheia Relay | Independently deployed encrypted transport; not a dependency of the 1.4.0 package or quickstart. |

Desktop must not read SQLite, scrape CLI output, or reproduce governance rules to work around missing service contracts. A missing feature is exposed through a reviewed API change, marked unavailable, or deferred.

## 4. Workstream A: Contract hardening

### CH-1. Define consumer profiles and capture the baseline

Create a machine-readable inventory mapping each selected operation to its request/response types, permissions, namespace/privacy behavior, errors, pagination, side effects, and tests.

Proposed profiles:

| Profile | Initial scope | Explicit limits |
| --- | --- | --- |
| `memory-read-v1` | Discovery, current principal, dashboard overview, search/retrieval, context packs, claim detail, explanation, and audit. | Client-neutral profile. A search-backed explorer is acceptable. Do not promise exhaustive claim browsing or full evidence detail unless corresponding contracts are available. |
| `memory-review-v1` | Candidate list/detail, promotion, and rejection, including stale-write protection and audit correlation. | Client-neutral profile. Extend later for claim edits and conflict resolution. Candidate inspection currently requires `memory:review`, not merely `memory:read`. |
| `agent-onboarding-v1` | Candidate-first remember, retrieval/context, provenance, and the selected starter integration operations. | Reuse the same operation schemas as Desktop where they overlap. Review remains a separate trusted action. |
| Future `relay-sync-v1` | Reserved planning area for federation transport consumers. | Not advertised as supported and not a 1.4.0 release gate. |

Profiles describe Memory capabilities, not approved application identities. Any authorized client can implement them; no profile or operation requires Desktop to be installed, registered, or running.

Start from existing routes such as `/v1/health`, `/v1/ready`, `/v1/version`, `/v1/compatibility/report`, `/v1/search` or `/v1/retrieve`, `/v1/context-pack`, `/v1/claims/{claim_id}`, `/v1/claims/{claim_id}/explain`, `/v1/audit/{target_type}/{target_id}`, `/v1/dashboard/overview`, `/v1/remember`, and the selected candidate routes.

Choose canonical routes for new examples without removing documented aliases. Profile coverage must describe actual endpoint and field guarantees, not only a list of route prefixes.

**Acceptance:** Every selected operation has an owner, explicit behavior, and a conformance-test reference. Existing v1 contracts remain supported. Broader features have a visible deferred-gap register.

### CH-2. Replace generic shapes with useful schemas

For profile operations, define:

- Stable operation IDs and explicit path/query/header parameters.
- Endpoint-specific request fields, required/optional rules, defaults, enums, limits, and validation behavior.
- Typed response payloads inside the existing success envelope.
- Redacted, omitted, nullable, and unavailable fields where governance changes what a caller can see.
- Actual error/status combinations, including validation, authorization, missing resources, conflicts, rate limits, and service unavailability where relevant.
- Precise pagination semantics: ordering, limits, continuation behavior, and termination.
- Structured permission requirements, including any-of/all-of and action-specific requirements rather than only human-readable strings.
- Request IDs and supported idempotency/concurrency headers.

Unrestricted metadata objects can remain extensible where intentional; primary request and domain result types must not collapse to arbitrary dictionaries.

Use one authoritative contract definition or an enforced reconciliation mechanism. Do not maintain a schema that drifts away from runtime behavior. Tightening a schema must not silently reject previously accepted legacy inputs; document legitimate extension fields and review validation changes for compatibility.

Preserve the existing `/v1/openapi.json` response behavior unless changed through an explicit compatibility decision. The current service wraps the schema in its response envelope, so the capture/build tool must extract the OpenAPI document before passing it to a generator.

Choose and pin a generator compatible with the selected OpenAPI format. Validate the schema, generate a TypeScript client, compile representative consumer calls, and execute those calls against a real local service. A schema snapshot or compilation alone does not prove the contract is correct.

**Acceptance:** Initial profiles generate useful types and execute without handwritten endpoint payload substitutions. Tests validate actual success, error, pagination, and redaction payloads against the published schema.

### CH-3. Separate versions and negotiate compatibility safely

Define these concepts explicitly:

| Concept | Meaning |
| --- | --- |
| Package/software version | Installed distribution version; service version may intentionally use the same value when shipped together. |
| API major | The HTTP protocol family, currently `v1`. |
| Database schema version | Actual persistent schema/migration state; it changes only when storage changes. |
| Consumer-profile version | The tested operation and behavior contract a consumer requires. |
| Service identity | An opaque identity used to distinguish connected instances for cache/context isolation; not a secret or a local database path. |

Resolve software version reporting from authoritative package/build metadata with a tested development fallback. Audit health, OpenAPI, compatibility reports, diagnostics, and release metadata for accidental reuse of the storage constant. Do not replace legitimate schema-version uses in migrations or backups.

The SDK transition is a release-critical requirement:

1. Add accurate, explicitly named software and profile fields.
2. Update new SDK compatibility logic to use API/profile support rather than software/schema equality.
3. Preserve the legacy compatibility-report fields needed by the published 1.3.1 SDK during the transition; label their historical meaning and deprecation clearly.
4. Correct the service-version endpoint without inadvertently breaking the separate legacy compatibility check.
5. Give new clients a documented limited-capability fallback for older services. Unsupported review features stay disabled; a package-number comparison must not falsely imply support.
6. Test both the 1.3.1 client against the new service and the new client against a 1.3.1 service.

Do not bump the database schema simply to match `1.4.0`. If revisions or instance identity require storage changes, review those changes separately and provide an explicit migration plan.

**Acceptance:** Canonical software reporting is accurate, schema reporting remains accurate, supported older clients continue to work, and Desktop can explain which required profile or feature is missing.

### CH-4. Complete principal and permission discovery

Add an authenticated, non-console-specific endpoint, provisionally `GET /v1/auth/me`, returning only safe current-principal metadata:

- Client/principal identity and authentication mode.
- Effective capabilities and namespace grant patterns.
- Effective privacy ceiling.
- Relevant expiration state and safe service identity/profile information, either directly or through the discovery contract.

Do not expose token values, token hashes, provider secrets, or another principal's grants. Keep the existing console-session endpoint compatible. Define anonymous/tokenless behavior explicitly rather than presenting it as an authenticated user.

The capability vocabulary comes from Memory. Correct the Desktop `memory:promote` assumption and publish a machine-readable operation-to-permission mapping. Account for effective administrative privileges, namespace checks, and privacy policy; a capability list alone is not a per-resource authorization guarantee.

Namespace grant patterns are not necessarily an enumerable namespace list. For the first Desktop slice, allow explicit namespace selection validated by the service. Add an authorized namespace-discovery endpoint only if a browsable selector is required; do not expose a global namespace inventory implicitly.

Document invalid, expired, revoked, disabled-client, and changed-permission behavior. Desktop must clear or isolate cached sensitive data when the principal, service, or effective scope changes.

**Acceptance:** An ordinary scoped token can discover its own effective access without admin rights, and negative tests prove that metadata and domain requests cannot cross authorization boundaries.

### CH-5. Define transport, reads, and recovery behavior

Choose the initial supported browser topology before implementing transport changes. Recommended starting point: a same-origin local web deployment or a controlled same-origin proxy to the Memory service. If the selected Desktop webview requires cross-origin requests, implement and test a narrow allowlist instead.

For a cross-origin mode, specify approved origins, preflight handling, allowed methods/headers, exposed response headers, and credential behavior. Do not use wildcard credential access or relax loopback/bind/authentication controls to make a demonstration work. Local unauthenticated deployment and cross-origin access need an explicit threat-model decision.

Test the chosen arrangement in an actual browser or selected desktop webview, not only through direct service calls. Keep sensitive responses out of shared/persistent caches and preserve the existing console's session/CSRF protections.

Define the client transport once: cancellation, bounded timeouts, retries, correlation IDs, envelope normalization, and actionable errors. Retry only where the operation is safe to replay. Preserve idempotency keys across uncertain write retries; never blindly replay a mutation with a new key.

Start live refresh with polling. Use bounded intervals/backoff, cancellation, and no overlapping requests. Refresh selected records after writes and on reconnection. Specify which retrieval/context requests are read-only and disable optional usage-recording side effects for background polling.

Existing pagination need not become cursor-based everywhere. Preserve supported behavior and define it honestly. If stable cursor pagination is needed for a selected workflow, add it compatibly rather than claiming it already exists.

**Acceptance:** The selected browser topology works with real authentication and headers; denied requests stay denied; polling does not introduce unintended memory mutations or excessive request volume.

### CH-6. Add stale-write safety for the review profile

Expose an opaque revision or equivalent concurrency token for selected mutable resources. Require new Desktop review clients to submit the version they inspected.

The server must atomically compare that version and apply the mutation. Every supported writer affecting the reviewed state, including embedded, CLI, service, and background paths, must invalidate the relevant revision. An application-process lock or a timestamp-only client comparison is not a substitute for a transactional guarantee.

Keep idempotency and concurrency separate:

- Idempotency prevents repeating the same operation after an uncertain response.
- Concurrency checks prevent acting on state that changed after the user reviewed it.
- A successful idempotent replay returns the original result; it must not become a stale-write error simply because the first submission changed the revision.

On stale state, reject the mutation with the chosen documented conflict/precondition response, preserve the resource, and let Desktop refresh and request another explicit decision. Do not force-apply, silently retry promotion, or automatically merge a governance decision.

Preserve old callers through additive preconditions on existing routes. If a new operation requires a precondition, expose that requirement through an explicitly negotiated contract instead of silently making an old optional input mandatory. Legacy unconditioned writes remain distinguishable from the stronger new-client guarantee.

**Acceptance:** Two-client and cross-writer tests prove stale decisions cannot commit through the new review workflow. Replays, authorization failures, transaction rollback, and audit records behave consistently.

## 5. Workstream B: Ease of use and the developer golden path

### DX-1. Establish one primary journey

Make the recommended starting point a single model-free, local Python tutorial using the installed PyPI package. A short CLI equivalent is secondary, not a competing first decision tree.

The complete learning journey is:

```text
Install -> open a demo database -> capture evidence/candidate
        -> inspect and explicitly approve -> retrieve lexical context
        -> inspect provenance -> reopen and verify persistence
```

Use one namespace, one known example, deterministic inputs, and a lexical query that actually matches the sample. Show the expected result and explain why it appears. Explicitly distinguish a pending candidate from a trusted claim.

The demonstration should keep the developer in control of promotion. An automated CI test may supply the documented review decision; an interactive starter must not silently approve unreviewed input.

The first success must require no account, API key, model download, embedding index, running external service, or network access after dependencies are installed. Do not imply that lexical retrieval provides arbitrary paraphrase understanding.

Treat five minutes as a target to validate, not an existing performance claim. Measure from a ready Python environment through installation/setup and the final result; report network installation time separately so results are interpretable.

**Acceptance:** A new developer can run the published journey, see provenance, and explain why the candidate did not become trusted until review. The automated version runs outside the repository from installed release artifacts.

### DX-2. Add convenience without changing trust semantics

Prototype the journey using existing public APIs first. Remove repeated namespace/configuration plumbing and manual ID copying with a small additive scoped helper only where the prototype proves it necessary.

Recommended helper responsibilities:

- Manage database lifetime and an explicit active scope.
- Capture structured candidate input with source evidence, or use the existing deterministic extraction path for a narrowly documented example.
- Return candidate/claim handles that avoid manual ID copying.
- Make review/promotion explicit and preserve reasons, provenance, and audit behavior.
- Expose retrieval/context results and source explanations through existing kernel operations.

Finalize names and signatures in a short API decision record before coding. The product review's illustrative `memory.context(...)` is not a current API guarantee; the existing method is `context_pack()`. Prefer existing names unless an additive alias provides a demonstrated benefit.

Do not change the active-write default of existing `Memory.remember()`. Label it as a trusted in-process/manual-write interface. The recommended agent helper should be explicitly candidate-first, and the agent/service example should use a restricted token. Embedded Python code remains trusted local code; a scoped helper is not an authorization sandbox.

Do not add a free-text `remember(anything)` promise that secretly depends on an LLM. Without a model, use explicit structured input or clearly bounded deterministic extraction.

**Acceptance:** Existing API/CLI/SDK tests retain their meaning; the easier path preserves governance; helper code delegates to existing domain behavior instead of duplicating it.

### DX-3. Improve setup and first-run diagnostics

Build on `aletheia init`, `doctor`, and existing configuration loading. Provide an obvious path to create a fresh demonstration database, inspect configuration, and understand why a step failed.

Diagnostics should distinguish:

- Unsupported Python/environment or missing package installation.
- Unwritable database path, locked database, or required migration.
- Service unavailable versus incompatible contract versus invalid credentials.
- Missing capability, namespace mismatch, or privacy restriction.
- Empty memory, pending candidates, and a lexical query with no match.
- Optional provider not configured, provider unavailable, or stale/mismatched semantic index.

Basic onboarding checks must not require admin permissions. Diagnostics should inspect safely by default; repairs, migrations, overwrites, network calls, and token provisioning must be explicit. Preserve existing command behavior where necessary by adding an explicitly read-only diagnostic mode.

Starter generation must not overwrite an existing database, project, or config without explicit consent. Use disposable demo data and document cleanup. Credentials belong in environment/secure configuration, not generated source files, committed examples, URLs, or diagnostic logs.

**Acceptance:** Each expected failure has a tested explanation and a safe next action. Missing optional AI configuration is not reported as failure of the zero-model installation.

### DX-4. Reorganize documentation and executable examples

Make the public documentation progressive:

1. Install from PyPI and complete the five-minute example.
2. Explain evidence, candidate, review, claim, retrieval/context, and provenance using that example.
3. Connect one agent through the HTTP SDK or generic adapter.
4. Enable semantic retrieval if needed.
5. Enable governed LLM extraction if needed.
6. Explore security, operations, federation, plugins, and full references.

Update README, installation, documentation index, integration guide, examples, and troubleshooting together. Put source/development installation after the public package path. Keep architecture contracts available but out of the first-run reading requirements.

Deliver three small, executable starters:

- Embedded Python, zero-model local memory lifecycle.
- HTTP/Python SDK agent with scoped, candidate-first writes and a separate operator review step.
- TypeScript consumer exercising the generated contract client and discovery/read workflow.

Reuse the existing example-generation infrastructure where practical. Support clean reruns and avoid placeholders that require manual ID hunting. Document packaging/runtime requirements rather than assuming access to the repository checkout.

Test code extracted from the actual published examples, not a separate approximation. Include source/provenance output and explicit limitations. Keep model-assisted examples in a distinct optional section.

**Acceptance:** Every primary example runs from the built distribution; README and bundled docs agree; no primary step assumes unreleased methods, mandatory models, or repository-only files.

### DX-5. Provide optional, tested AI setup recipes

Offer progressive enhancement without changing the default:

| Tier | Experience | Required model |
| --- | --- | --- |
| Core | Explicit or deterministic candidate creation, review, lexical retrieval, and context/provenance. | None. |
| Semantic | Meaning-based and hybrid retrieval using an explicitly selected embedding provider. | Embedding model only. |
| AI-assisted | LLM extraction/suggestions, still candidate-first and review-governed. | LLM; embeddings only if semantic retrieval is also enabled. |

For 1.4.0, deliver one tested local embedding recipe and one tested local LLM recipe using existing provider mechanisms. These recipes are optional for users, but validated recipe documentation is part of the planned release scope. A hosted recipe may follow without delaying the base release.

Select actual model/provider versions during execution after checking availability, license, hardware needs, installation size, and input/output behavior. Record the tested configuration, date, limitations, locality, expected resource use, and data-handling implications. This plan deliberately does not freeze model recommendations without that validation.

Provider setup should show what will be downloaded or contacted, require deliberate opt-in, and verify the connection using non-sensitive sample input. Never silently switch to a hosted provider if a local one fails.

For embeddings, validate dimensions/index compatibility and explain reindexing. For LLMs, show the candidate output and review boundary rather than treating generation as truth. Do not present `local_hash` or deterministic mocks as production-quality semantic intelligence.

Prefer recipes and validated configuration presets over a new installation subsystem. Add an optional packaging extra such as `[local-ai]` only if it contains real, justified dependencies and has its own installation tests; do not document a nonexistent extra.

**Acceptance:** Core tests remain deterministic and model-free. Each advertised recipe has a separately recorded live smoke test, including safe failure behavior. Recipe setup never weakens namespace/privacy policy or introduces default external calls.

## 6. Readiness gates and the Desktop dependency boundary

| Gate | Required evidence | What it unlocks |
| --- | --- | --- |
| G0: scope and decisions | Profile inventory, API/write-semantics decisions, transport choice, compatibility-transition design, and baseline fixtures. | Implementation can proceed with a stable scope. |
| G1: discovery foundation | Correct canonical versions, legacy SDK bridge, complete principal metadata, and schema generation for discovery. | Desktop connection/identity workflow and integration test harness. |
| G2: read integration | Typed read profile; real generated-client calls; scope/redaction/error/pagination tests; selected browser transport; polling behavior. | Read-only Desktop explorer, detail, context, and provenance features. |
| G3: governed writes | Review profile; atomic revisions; permission enforcement; idempotent replay; stale-write recovery; audit tests. | Desktop candidate review/promotion/rejection. Other mutations require their own equivalent gate. |
| G4: first-run experience | Installed-package tutorial, agreed public API/helper path, scoped agent starter, diagnostics, and executable docs. | Public developer golden path. |
| G5: optional AI recipes | Separate validated local embedding and LLM smoke tests plus explicit setup/privacy documentation. | Recommended opt-in semantic and AI-assisted paths. |
| G6: release | Backward-compatibility matrix, regression/packaging/migration gates, standalone-operation proof without Desktop, complete release documentation, and release approval. | Publish Memory 1.4.0 and declare its supported client-neutral profiles. |

Desktop scaffolding, design-system work, navigation, and static/mock layouts can proceed before G1. API-backed read features require G2. Real review workflows require G3. Neither event streaming nor Relay readiness is a prerequisite for these gates.

Desktop may develop against pinned prerelease artifacts after the relevant gate, but its production release should depend on a published, compatible Memory version. Passing one profile does not certify all Desktop workspaces.

The "unlocks" column describes downstream opportunities only. None of the Desktop work listed there is required to pass Memory's gates or publish Memory independently.

## 7. Recommended execution roadmap

Execute by dependency and evidence, not by a speculative calendar. Estimate duration after Phase 0 inventories endpoint and migration work. The two workstreams can proceed concurrently where dependencies allow, while retaining their own acceptance gates.

| Phase | Work and concrete deliverables | Dependencies | Exit condition |
| --- | --- | --- | --- |
| 0. Baseline and scope | Freeze the first three profiles; capture schemas/responses; retain 1.3.1 client fixtures; record transport, API, and compatibility decisions; prototype and time the first-run journey. | Current baseline. | G0; agreed must-haves and explicit deferrals. |
| 1. Shared discovery and early onboarding | Implement CH-3/CH-4; add the discovery schemas; correct stale PyPI messaging; write the canonical tutorial draft and scoped-helper specification. | Phase 0. | G1; old-client compatibility demonstrated; no new write behavior hidden in examples. |
| 2. Read-contract vertical slice | Complete CH-2/CH-5 for the read profile; generate/compile the TypeScript client; test real browser reads, error/redaction cases, and polling. | Phase 1. | G2; Desktop read-only integration can begin. |
| 3. Zero-model experience | Deliver DX-1 through DX-3 and the embedded/HTTP portions of DX-4: additive helper if justified, safe initialization, diagnostics, starters, and executable tutorial tests. | Phase 0 decisions; Phase 1 discovery for the service starter. Can overlap Phase 2. | G4; installed-package first-run journey is complete. |
| 4. Governed review contracts | Deliver CH-6 and typed review operations; test cross-writer revision invalidation, stale decisions, replay, permissions, and audit. | Phase 2 contract/transport foundation. | G3; Desktop review integration can begin. |
| 5. Optional providers and complete examples | Select/test local recipes; document explicit opt-in and safe failures; finish TypeScript starter and progressive documentation. | Phase 3 core journey; Phase 2 generated client. Recipe evaluation can overlap Phase 4. | G5; optional AI paths do not affect core installation. |
| 6. Release-candidate integration | Build installable prerelease artifacts; run all profiles, client-version combinations, migration/rollback checks, and fresh-environment examples using Memory-owned generic client harnesses; prove standalone operation with no Desktop checkout or installation. | Phases 2-5 complete. | All Memory release criteria met; no undocumented contract exceptions or dependency on Desktop progress. |
| 7. Release and handoff | Review changelog/compatibility matrix; obtain release approval; merge through protected-branch workflow; publish tagged artifacts using the existing publishing process; verify the installed public package. | Phase 6 and explicit release authorization. | G6; Memory 1.4.0 published independently with supported-profile evidence and integration notes for any client. |

### Critical paths

```text
Scope -> discovery -> typed read contract + transport -> read-only Desktop
                              |
                              +-> review contract + revisions -> Desktop writes

Scope -> zero-model journey -> safe helpers + diagnostics -> executable docs
                                                    |
                                                    +-> optional AI recipes

All agreed gates -> release candidate -> approved Memory 1.4.0 release
```

Do not serialize all onboarding behind full API coverage. Documentation cleanup and the embedded example can progress early. Conversely, do not use the quickstart as a reason to bypass the contract or governance gates.

If release scope must be reduced, remove or defer a whole advertised capability and update the profile/roadmap explicitly. Do not ship partial write safety as if the review profile had passed. SSE, hosted-provider recipes, Relay profiles, and broad administrative coverage are the first candidates to remain deferred; they are not required scope here.

## 8. PR, branch, and release strategy

Keep the existing protected-branch workflow. Implementation should use task-specific branches/worktrees from the latest approved baseline, with names such as `codex/v1.4-discovery`, `codex/v1.4-read-contract`, and `codex/v1.4-onboarding`. These names are suggestions; this document does not create branches.

Recommended reviewable PR sequence:

1. Approved scope, profile inventory, baseline fixtures, and contract-generation test harness.
2. Version reporting and SDK compatibility bridge.
3. Principal discovery and canonical capability metadata. A companion Desktop documentation correction belongs in its own repository and does not block the Memory PR or release.
4. Typed discovery/read schemas and reproducible TypeScript-client verification.
5. Selected browser transport, errors/pagination, and polling contract tests.
6. Zero-model tutorial, additive convenience helper, diagnostics, and executable examples; split if needed for reviewability.
7. Review revisions/preconditions and complete typed review-profile tests.
8. Optional provider recipes and final progressive documentation.
9. Release-candidate evidence, compatibility matrix, changelog, and packaging updates.

Each PR should include its relevant tests and documentation rather than postponing correctness to the final integration phase. Downstream PRs should reference exact schema/profile versions and remain independently buildable. Memory PRs and required CI must not depend on merging or running a Desktop PR.

Small additive changes may merge to `main` after their own gates. Do not merge half-implemented public contracts, disable protections, or rely on a large final cleanup PR. If a change cannot stand alone, use an explicitly managed dependent PR sequence until it is releasable.

The current release workflow checks the baseline boundary, tests Python 3.11-3.13, and builds artifacts. Extend it with profile validation, TypeScript generation/compilation, actual-service contract tests, and clean-install examples. Model-dependent smoke tests belong in a separate explicitly configured job; ordinary CI must not need model credentials or heavy downloads.

A docs-only correction can ship earlier without waiting for 1.4.0. This does not mean repeating already-completed 1.3.1 publication work; the new clean-install gate verifies new release artifacts.

## 9. Compatibility and verification matrix

| Test dimension | Minimum evidence |
| --- | --- |
| Standalone independence | Install, initialize, capture/review, retrieve/contextualize, inspect provenance, restart, and run required tests with the Desktop repository/application absent. Memory's release pipeline checks out only Memory. |
| Published legacy Python SDK -> new service | Existing supported workflows remain usable; the legacy version-equality check does not falsely reject the service. |
| New SDK -> 1.3.1 service | Documented limited-feature behavior; absent principal/profile/revision capabilities produce explicit degradation or refusal, not invented support. |
| New TypeScript client -> new service | Discovery, read, onboarding, and selected review operations execute using generated types and real HTTP responses. |
| Authorization and privacy | Ordinary/scoped/read-only/review/admin cases; denied namespaces; privacy ceilings; expired/revoked credentials; no sensitive error or diagnostic leakage. |
| Schema conformance | Actual requests/responses/errors match published types, including nullable/redacted fields and pagination boundaries. |
| Concurrency and retries | Two clients, other core writers, stale revisions, duplicate submission, uncertain responses, rollback, and consistent audit outcomes. |
| Browser behavior | Real chosen topology with auth, required headers, origin restrictions if applicable, cancellation, and no unsafe persistent caching. |
| Model-free onboarding | No external calls after installation; explicit review; real lexical results, provenance, persistence, and clear empty/error states. |
| Package distribution | Built wheel and source distribution install in fresh environments; all primary examples and bundled documentation are available without source-tree imports. |
| Storage compatibility | Upgrade a representative 1.3.1 database if storage changes; preserve data, provenance, permissions, and retrieval. Verify backup/restore recovery and older-binary refusal if downgrade is unsupported. |
| Optional AI | Separately recorded local embedding/LLM recipe smoke tests; explicit opt-in, provider failure, dimension/index mismatch, and governance preservation. |

Do not declare a finding closed because one narrow fixture passes. For each acceptance criterion, test the behavior class and sibling paths, record the evidence, and identify any remaining limitation. This follows the lesson documented in the existing v1.3.0 postmortem.

## 10. Main risks and decisions to resolve

| Risk or open decision | Recommended treatment |
| --- | --- |
| All 199 paths become a prerequisite. | Freeze first-consumer profiles in Phase 0 and expand coverage incrementally without weakening existing support promises. |
| Correct version fields break old SDK compatibility. | Implement and test the legacy-field bridge before changing compatibility assumptions. |
| A simpler API bypasses governance. | Keep candidate and active-write semantics explicit; preserve old `remember()` behavior; test lifecycle outcomes. |
| Schema and runtime diverge. | Use one authoritative definition or mandatory runtime conformance tests; generated files alone are not proof. |
| Revision protection misses CLI/background writes. | Place revision invalidation at the domain/storage boundary and test all supported mutation paths for profiled resources. |
| Browser support broadens local attack surface. | Select a narrow topology; require an explicit origin/authentication threat-model review. |
| Optional AI becomes mandatory or silently external. | Keep core tests/setup model-free and provider activation explicit; no automatic hosted fallback. |
| First-run setup changes existing user data. | Use a separate demo target, non-destructive defaults, and explicit repair/migration actions. |
| Desktop requests every planned workspace immediately. | Maintain its gap register; missing provider/index/evidence/admin features remain unavailable or deferred until their contracts pass. |
| Generated client ownership or publishing grows scope. | Memory owns schemas and conformance; Desktop consumes pinned generated output initially. A public npm package is a later decision, not required for 1.4.0. |
| Memory becomes coupled to Desktop delivery. | Use client-neutral profiles and Memory-owned generic harnesses. Desktop integration and UI release gates live exclusively in Desktop. |

Phase 0 must settle the exact helper API, initial operation list, version-field transition, browser topology, revision strategy, generator/toolchain, and supported compatibility matrix. Model selection can be finalized during Phase 5 evaluation, before a recipe is advertised.

## 11. Definition of done

- [ ] Memory installs, builds, runs, tests, and releases without the Desktop repository or application.
- [ ] Client-neutral read, review, and agent-onboarding profiles are explicit, versioned, and supported by Memory-owned actual-service tests.
- [ ] Canonical software/API/schema/profile metadata is accurate and older SDK behavior remains compatible.
- [ ] Normal tokens can discover their own identity, effective capabilities, namespace grants, and privacy ceiling safely.
- [ ] Memory documentation and generated metadata use its real permission vocabulary; downstream documentation alignment is communicated without gating Memory's release.
- [ ] The selected browser transport works without weakening security defaults.
- [ ] Every mutation advertised in the review profile has atomic stale-write handling, replay behavior, and audit coverage.
- [ ] One deterministic, model-free tutorial demonstrates the full evidence-to-reviewed-context lifecycle and persistence.
- [ ] Convenience APIs and setup changes are additive, tested, and do not alter trusted-versus-candidate write meaning.
- [ ] README, bundled docs, diagnostics, and all primary examples match the installed release.
- [ ] Optional local embedding and LLM recipes are tested separately and remain opt-in.
- [ ] Existing regression gates plus new contract, compatibility, browser, packaging, and migration gates pass.
- [ ] Any unresolved gap is explicitly excluded from advertised support and represented in the follow-on roadmap.
- [ ] Release approval, protected-branch merge, tagged publication, and verification of the new public artifact are complete before calling 1.4.0 shipped.

## 12. Recommended roadmap after 1.4.0

1. **Aletheia Desktop read-only alpha:** connection, scope/identity display, search-backed Memory Explorer, claim detail, and provenance using `memory-read-v1`.
2. **Desktop governed-review beta:** candidate review/promotion/rejection using `memory-review-v1`, with stale-state recovery and explicit audit-aware actions.
3. **Measured integration expansion:** add provider/index management, deeper evidence browsing, conflict workflows, and operational screens only as validated user needs justify their contracts.
4. **Optional real-time updates:** add event streams when polling cannot meet demonstrated status/latency needs; preserve a fallback where appropriate.
5. **Federation transport foundation:** harden pairing/sync protocol requirements in Memory, define a tested Relay consumer profile, and build the encrypted relay as a separate service.
6. **Desktop multi-device experience:** pairing, device trust/grants, sync status, revocation, and conflict handling after the corresponding Memory/Relay contracts are ready.

This sequence advances the product review's direction in order: make Aletheia easier to adopt, make its memory visible and governable, then connect installations without centralizing memory authority.

## 13. Source context

This plan synthesizes the user-provided **Aletheia Memory v1.3.1 Product Review** (`version1.3.1_product_review.md`), the contract-gap assessment, and the current repository. The supplied review is an external planning input, not assumed to be distributed with the package.

Key in-repository references:

- [Package metadata](../pyproject.toml)
- [Current README and quickstart](../README.md)
- [Installation guide](installation.md)
- [Integration guide](integration_guide.md)
- [Examples infrastructure](examples.md)
- [Documentation index](index.md)
- [Public stability policy](v1_public_contracts.md)
- [HTTP routing, discovery, and schema generation](../aletheia/service/http.py)
- [Authentication and capability definitions](../aletheia/service/auth.py)
- [SDK compatibility and candidate/active-write helpers](../aletheia/client.py)
- [Memory lifecycle and embedded API](../aletheia/core/memory.py)
- [CLI initialization, diagnostics, and example commands](../aletheia/cli/main.py)
- [Existing release gates](../.github/workflows/release-gates.yml)
- [Existing publication workflow](../.github/workflows/publish-pypi.yml)
- [Contribution boundaries](../CONTRIBUTING.md)
- [Historical remediation and verification lessons](v1_3_0_postmortem_and_followups.md)

Companion planning inputs in the separate `aletheia-desktop` repository are `docs/architecture/06-state-and-data-management.md`, `07-api-integration-architecture.md`, and `14-implementation-plan.md`. They guide consumer needs but do not override Memory's published contracts or authorize bypassing its service boundary.
