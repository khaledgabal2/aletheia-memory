# Migration Guide

Aletheia 1.7.0 uses storage 1.3.1 and API v1. Upgrades from 1.6.x do not
change the storage version. Read the [1.7.0 upgrade guide](v1_7_0_upgrade.md)
and keep a verified pre-upgrade backup. The milestone history below explains
how earlier schema versions were introduced.

M12 upgrades the schema target to `1.3.0` and backfills governed LLM records:

- LLM prompt and prompt-version provenance tables.
- LLM run, output, and safety-flag tables.
- Public contracts for governed LLM providers, candidate extraction, provenance, and CLI commands.
- Metadata-only persistent LLM output records by default; full output persistence requires explicit local opt-in with `ALETHEIA_LLM_OUTPUT_STORAGE=full`.
- Compatibility and conformance records for the current v1.4.0 software platform.

It does not call LLM providers, extract new memories, promote candidates, summarize evidence, resolve conflicts, or send any data over the network automatically.

M11 previously upgraded the schema target to `1.2.0` and backfilled production semantic retrieval records:

- Embedding metadata and semantic index lineage columns.
- Provider type/version, input hash, privacy level, vector store, index version, status, and stale reason metadata.
- Semantic index records for status, verification, stale marking, and pruning.
- Compatibility records for the v1.2.0 platform.

It does not generate embeddings automatically, call external providers, create federation identities, add peers, create share grants, or enable sync automatically.

M10 previously upgraded the schema target to `1.1.0` and backfilled local-first federation records:

- Federation public contracts and API contract versions.
- Trust domains and import trust policies.
- Federation conformance suites.
- SDK and compatibility records for federation-beta.

M9 previously upgraded the schema target to `1.0.0` and backfilled stable platform records:

- Public contracts.
- API contract versions.
- Compatibility matrix entries.
- Plugin, conformance, SDK, docs, doctor, and v1 gate catalogs.

Plan and apply:

```bash
aletheia migrate plan --db ./aletheia.db --target-version 1.3.1
aletheia migrate apply --db ./aletheia.db --target-version 1.3.1 --backup-before --verify-after
```

After migration:

```bash
aletheia compatibility report --db ./aletheia.db
aletheia doctor --db ./aletheia.db
```

## Predicate declaration storage

Predicate semantics adds the `predicate_semantics` table and review invalidation
triggers within storage version `1.3.1`. The version string alone does not prove
that this additive schema setup is present. Normal embedded opens with automatic
migration enabled install it transactionally.

For a service configured with automatic migration disabled, stop the service,
provide a backup passphrase through `ALETHEIA_BACKUP_PASSPHRASE` (or the existing
stdin option), and explicitly upgrade before restarting:

```bash
aletheia migrate apply --db ./aletheia.db --backup-before --verify-after
```

Keep the encrypted pre-migration archive and the matching older binary for
recovery. Claims, evidence and candidate data are preserved; outstanding review
snapshots are invalidated. Starting against the older table/trigger inventory
with automatic migration disabled fails closed and directs the operator to
migrate. In-place downgrade remains unsupported.
