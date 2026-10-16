# Upgrade to 1.6.2

Version 1.6.2 fixes HTTP semantic provider selection and fallback reporting from
issue #64. Python remains 3.11+, the API remains v1, and storage remains 1.3.1.
No database migration or new Desktop permissions are required.

Upgrade the service's own Python environment:

```bash
python -m pip install --upgrade aletheia-memory==1.6.2
```

Restart the service with an explicitly selected provider:

```bash
export ALETHEIA_SEMANTIC_PROVIDER=ollama_style
```

Alternatively set `semantic_provider = "ollama_style"` under `[server]` in the
service TOML configuration. Continue using the existing
`ALETHEIA_EMBEDDING_OLLAMA_STYLE_*` endpoint, model, dimensions and document/query
prefixes that created the index. Provider-specific environment variables alone
do not enable external calls; the default server provider stays `mock`.

Both `/v1/retrieve` and `/v1/search` use this server choice. Existing Desktop
requests work without a consumer change or permission expansion. Clients cannot
change provider endpoints or credentials through retrieval request extensions.

Fallback results now report `retrieval_mode: "lexical"`. The additive
`semantic_status` is `indexed` for a positive vector match, `unavailable` when
that claim has no positive vector match, and `not_requested` for lexical
requests. Do not treat a requested mode or a zero score as proof of embedding
use. Empty result lists remain empty. Configured HTTP-provider dimensions and
input presets must match the index; incompatible settings require explicit
reindexing. Corrections can appear as lexical fallback while awaiting indexing.

Back up important memory before an upgrade. The existing access, archive and
caller compatibility guidance from [1.6.1](v1_6_1_upgrade.md) still applies.
See the [verification record](issue_64_verification.md) for automated and actual
installed Desktop/Nomic acceptance evidence.
