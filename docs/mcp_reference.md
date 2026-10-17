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

## Stdio protocol

The stdio server waits for the client and emits no unsolicited greeting. Send
JSON-RPC `initialize` with `protocolVersion`, `capabilities`, and `clientInfo`,
then `notifications/initialized`. Supported versions are `2025-06-18` and
`2024-11-05`; an unsupported version is offered `2025-06-18` for negotiation.
`tools/list` returns mode-filtered tools with JSON Schema `inputSchema` fields.
`tools/call` returns MCP text content, optional object `structuredContent`, and
`isError`. Tool execution still enforces token, namespace, privacy and write-mode
checks. `ping` is supported. This implementation advertises tools only; it does
not advertise subscriptions, resource/prompt servers, or task execution.

Frames are bounded to 1,048,576 characters. Malformed JSON and invalid method
arguments receive JSON-RPC errors; denied tool executions return `isError=true`.
Requests are processed serially. The legacy `{"tool":"memory_search",
"arguments":{"query":"example"}}` input remains supported before initialization,
without the former unsolicited ready line. Consumers should use JSON-RPC.

The built-in conformance suite exercises actual protocol parsing using isolated
streams; the beta interoperability script uses the official Python MCP SDK
against an installed wheel through a real subprocess.
