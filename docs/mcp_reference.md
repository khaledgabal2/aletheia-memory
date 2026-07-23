# MCP Reference

Run the local MCP tool registry:

```bash
aletheia mcp --db ./aletheia.db --mode read_write_candidate --list-tools
```

Stable v1 MCP behavior:

- Read tools return context, retrieval results, health, and provenance without modifying memory.
- Candidate-write tools store reviewable candidate memories.
- Active-write behavior requires explicit elevated mode and remains governed by review/audit policy.
- Tool invocation logs are stored locally.
- Governed LLM tools expose query expansion and review-only entity, category, scope, and duplicate-merge suggestions.

The conformance suite checks that core context-pack MCP tooling is available.
