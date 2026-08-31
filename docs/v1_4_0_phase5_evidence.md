# Phase 5: optional providers and complete examples

Recorded 2026-08-30 (America/Chicago; report timestamps use UTC). Implementation
starts after Phase 4 commit `0c48452e93f02c614ab1aef04e6829cc50bfa9ee` on
`codex/v1.4-providers-and-examples`. No merge or publication is authorized here.

## Delivered scope

- `agent-onboarding-v1`: typed, explicitly keyed candidate creation; current
  scoped authorization before creation/replay; atomic evidence/candidate/audit/
  receipt; no active-write or review grant to agents. The SDK refuses unsupported
  profiles and candidate-helper active-write overrides. Legacy extensions remain
  accepted; profile negotiation does not erase the legacy API.
- Packaged TypeScript agent with generated schema and locked Node dependencies.
  Python and TypeScript agents run separately from the operator; creation and
  revision-checked review retain explicit keys. No automatic write retry or
  implicit approval. All three starters are available without the repository.
- Optional loopback-only HTTP provider transport, document/query prefixes and
  model revision in embedding index identity, explicit mismatch refusal/reindex,
  finite dimension checks, and full structured extraction schemas. Defaults remain
  model-free; no heavy Python dependency, fake extra, download or hosted fallback.
- A packaged, explicit-opt-in synthetic local recipe checker and progressive
  documentation covering locality, licenses, digests, sizes, privacy and failure.
  Ordinary tests use deterministic fixtures; the optional live CI workflow is
  manual, main-only and disabled unless a maintainer configures its runner/variable.

## Evidence

- Full Python 3.13 regression suite: **269 passed**, including 17 onboarding
  contract cases, eight provider cases and TypeScript starter generation safety.
  The final generation-schema constraint was additionally checked by all 22
  governed-LLM/provider tests. The full final matrix is repeated in Phase 6.
- All five generated TypeScript consumers pass against actual Memory HTTP:
  baseline, discovery, read, governed review, and onboarding. Five Node transport/
  polling lifecycle tests pass. The packaged schema matches fresh generated output.
- Prospective agent profile tested with both actual starter sources before being
  advertised. Installed wheel and installed sdist then each pass 11 Python
  onboarding checks, and separately 11 checks with the TypeScript starter.
  Each run covers approve/decline, empty trusted recall, source/provenance,
  persistence, revoked demo tokens and safe reruns. Python runs took 3.4 seconds;
  TypeScript runs including cached npm installation/compilation took 8.6–8.7 seconds.
  These are automated warm-cache timings, not human first-run or network timings.
- Wheel and sdist inspected: generated TypeScript source/schema/lockfile included;
  no node_modules, compiled dist, bytecode or database. Fresh environments install
  core dependencies only; the tutorial runs with socket connections blocked.
- [Live synthetic report](../contracts/v1.4.0/evidence/local-model-smoke.json):
  Ollama 0.32.14, Nomic v1.5 768-dimensional embeddings, Llama 3.1 8B Q4_K_M.
  Two paraphrased queries find the expected claims; wrong dimensions/preset and
  unavailable provider fail safely, and explicit reindex succeeds. Three LLM
  samples produce evidence-linked pending candidates with no warnings or active
  claims; a missing model and secret source produce no candidate. Combined run
  16.055 seconds. Sampled model VRAM: embedding 370,031,984 bytes; LLM
  5,263,327,231 bytes. Sampling is not a precise process/OS peak-memory measurement.
  No model downloads occurred. Tests used synthetic temporary databases only.

## Evaluation failures and limits

The initial Qwen 0.6B evaluation failed evidence offsets, allowed memory-type
selection and source-meaning retention in different attempts; it is not the
recommended extraction recipe. Initial Llama attempts also produced invalid,
empty claim fields. Memory retained the invalid candidate state without making
active claims. Full field constraints now include nonempty generated strings.
An early combined harness also put embedding seed claims into the extraction
namespace; the durable checker now isolates these independent recipes. Do not
infer broad accuracy from the passing three-sentence smoke test. Reports retain
warnings and candidate states, and failed samples cause a nonzero exit.

Local-only transport cannot police a separately operated model runtime. The
runtime must be trusted and deliberately configured. Changing a model requires
revalidation; outside this checker, model revision is operator-supplied metadata.
Privacy/review rules remain in force even for local inference.

GitHub Actions do not run in the private security fork. These macOS results are
not Linux CI evidence. Human five-minute onboarding, cold-network installation
timing, final independent CI, protected-branch merge and publication remain
release/handoff work. This evidence does not declare G6 complete.

## Reproduce

Use the [contract tooling guide](../contracts/typescript/README.md), then:

```sh
python -m pytest
python scripts/v1_4_onboarding_check.py --python /fresh/core-only-wheel/bin/python
python scripts/v1_4_onboarding_check.py --python /fresh/core-only-sdist/bin/python --typescript
python -m aletheia.local_recipe --allow-local-models --report new-synthetic-report.json
```

The last command is optional model use, not part of ordinary regression tests.
Install/compile the TypeScript toolchain only for that starter or conformance job.
