# Optional local model recipes

Start with the [model-free quickstart](quickstart.md). These recipes require Memory
1.4.0 or later and deliberately selected local models. Python core
installation downloads no model and needs no Node, Ollama or hosted account.
There is no `[local-ai]` extra: these adapters use the existing HTTP providers
and Python standard library, with no justified additional Python dependency.

## Tested selections

The live synthetic checks use Ollama 0.32.14 on macOS 26.5.1, Apple M4 Max,
16 CPU cores, 48 GiB unified memory. These are smoke checks, not a benchmark or
a minimum-hardware guarantee. Exact digests, candidate outputs, dimensions,
latency and sampled runtime model memory are recorded with the Phase 5 evidence.

| Purpose | Local model | Installed weights | Configuration |
| --- | --- | --- | --- |
| Embeddings | `nomic-embed-text:latest` (v1.5, 137M, F16) | 274,302,450 bytes | 768 dimensions; document/query prefixes; 2,048-token context |
| Extraction | `llama3.1:8b` (Q4_K_M) | 4,920,753,328 bytes | JSON schema output; 4,096-token context; 2,048 output tokens; temperature 0; 60-second request timeout; unload after each request |

Nomic is Apache 2.0 and requires different document/query prefixes; see its
[official model card](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5).
Llama uses the [Llama 3.1 Community License](https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct/blob/main/LICENSE),
not Memory's MIT license; read its terms and acceptable-use policy before use.
The [Ollama model listing](https://ollama.com/library/llama3.1:8b) identifies the
quantization and weight size. We do not bundle or redistribute either model.
Allow runtime headroom beyond the weight sizes; the tested LLM occupied about
5.3 GB of model memory as sampled from Ollama, excluding total process/OS memory.
A small `qwen3:0.6b` alternative was evaluated and is not recommended here: it
failed to preserve source meaning reliably. Llama also produced invalid outputs
during evaluation; stronger structured constraints help, but review is essential.

## Deliberate setup and verification

Install Ollama using its [official instructions](https://docs.ollama.com/quickstart)
and run a trusted local runtime on `http://127.0.0.1:11434`. Keep it on loopback;
Memory does not authenticate that runtime or configure its logging/telemetry.
If you choose to download these weights, the following commands contact Ollama's
model registry and consume roughly 5.2 GB plus metadata/cache space:

```sh
ollama pull nomic-embed-text:latest
ollama pull llama3.1:8b
```

These downloads are optional, manual steps. This implementation's evaluation
used already-installed models and downloaded zero model bytes. Tags can change;
the checker refuses a digest mismatch rather than accepting an untested model.
The accepted full digests are:

```text
nomic-embed-text:latest  0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f
llama3.1:8b             46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e
```

Run the packaged recipe with an explicit opt-in and a new report path:

```sh
python -m aletheia.local_recipe --allow-local-models --report local-smoke.json
# Either tier can be tested independently:
python -m aletheia.local_recipe --allow-local-models --task embedding
python -m aletheia.local_recipe --allow-local-models --task llm
```

It sends fixed synthetic input only, creates and discards its own database,
checks installed digests, refuses existing report paths, and never pulls models.
Separate namespaces isolate retrieval seed claims from extraction candidates.
Failed checks return a nonzero status; inspect the report and keep validation
intact. Results include candidate states and warnings, including failed samples.
No secret source is submitted for inference. Generated candidates remain under
normal governance, and the checker never promotes them. The missing-model check
must fail without a hosted fallback; lexical retrieval remains usable when an
embedding endpoint is unavailable. No user's existing database is opened.

## Apply the embedding preset deliberately

For an application you control, set these variables in that process only:

```sh
export ALETHEIA_EMBEDDING_OLLAMA_STYLE_ENDPOINT=http://127.0.0.1:11434/api/embed
export ALETHEIA_EMBEDDING_OLLAMA_STYLE_MODEL=nomic-embed-text:latest
export ALETHEIA_EMBEDDING_OLLAMA_STYLE_DIMENSION=768
export ALETHEIA_EMBEDDING_OLLAMA_STYLE_DOCUMENT_PREFIX='search_document: '
export ALETHEIA_EMBEDDING_OLLAMA_STYLE_QUERY_PREFIX='search_query: '
export ALETHEIA_EMBEDDING_OLLAMA_STYLE_MODEL_REVISION=0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f
export ALETHEIA_EMBEDDING_OLLAMA_STYLE_LOCAL_ONLY=true
```

Then explicitly call `memory.index_semantic(namespace, provider="ollama_style")`
and `memory.retrieve(namespace, query, mode="semantic", semantic_provider="ollama_style")`.
Only do this for data you have authorized the local runtime to process. The
preset signature includes both prefixes and model revision. Changing/removing
it, or changing dimensions, refuses incompatible query reuse and requires an
explicit reindex. Preserve a backup before rebuilding a real index. The revision
variable records your verified model identity; outside the smoke checker, Memory
does not independently attest the bytes loaded by your runtime. Same tags may
serve different models, so recheck the digest before reusing an index.
`local_hash` remains a deterministic test provider, not this semantic recipe.

For extraction, configure `ALETHEIA_LLM_OLLAMA_STYLE_ENDPOINT` to
`http://127.0.0.1:11434/api/chat`, `MODEL=llama3.1:8b`, `LOCAL_ONLY=true`,
`STRUCTURED_OUTPUT=true`, `NUM_CTX=4096`, `KEEP_ALIVE=0`, and `TIMEOUT=60`
under the same `ALETHEIA_LLM_OLLAMA_STYLE_` prefix. Then explicitly ingest evidence
and call `memory.extract_candidates(namespace, batch_id=batch.id, extractor="ollama_style")`.
Inspect run warnings, candidate status, exact evidence spans and provenance
before a separate human review. Do not promote based solely on valid JSON.

Local-only mode refuses non-loopback addresses, hostnames, redirects and proxies
on every request. It prevents these adapters from silently switching to a remote
endpoint; it cannot constrain what a separately operated model runtime does.
Protected-mode, namespace and privacy policy still apply. The default secret
extraction policy remains blocked. Keep model reports synthetic and out of
ordinary diagnostic bundles. Regular CI uses deterministic HTTP fixtures; the
live smoke job is separately dispatched on a deliberately provisioned runner.

The optional workflow requires a maintainer-provisioned macOS/ARM64 runner with
label `aletheia-local-models`, exact installed models, repository variable
`ALETHEIA_LOCAL_MODELS_ENABLED=true`, and a reviewed `local-model-smoke`
environment. It accepts manual dispatch from `main` only and an explicit
`allow_local_models` input. No runner, variable or environment was provisioned
by this change; local recipe evidence was collected separately. Regular PR jobs
never need this runner or model credentials.
