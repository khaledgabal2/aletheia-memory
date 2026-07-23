# Adapter Developer Guide

Agent adapters should read context packs and write candidate memories by default. Promotion to active or core memory remains a human or governed review action.

Create a scaffold:

```bash
aletheia adapters scaffold --db ./aletheia.db --type generic-http --name demo-adapter --output ./examples/demo-adapter
```

Run conformance:

```bash
aletheia adapters test ./examples/demo-adapter --db ./aletheia.db
aletheia adapters certify ./examples/demo-adapter --db ./aletheia.db
```

The scaffold includes an `agent_loop.py` that uses `AletheiaClient.context_pack` and `AletheiaClient.remember_candidate`.
