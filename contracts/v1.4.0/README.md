# 1.4 contract records

`profiles.json` is the frozen Phase 0 scope proposal. Its operation names and
"not advertised" status describe that baseline, not current service readiness.
Do not use it to decide which features a running service supports.

Discover current support with `/v1/auth/me` and use the actual service OpenAPI.
The 1.4.0 implementation advertises:

- `memory-read-v1`: [contract](../../docs/v1_4_0_read_contract.md)
- `memory-review-v1`: [contract](../../docs/v1_4_0_review_contract.md)
- `agent-onboarding-v1`: [contract](../../docs/v1_4_0_agent_onboarding_contract.md)

The authoritative service registries and Memory-owned projection harnesses emit
schemas for the [generated TypeScript tooling](../typescript/README.md).
`evidence/local-model-smoke.json` is an explicitly configured synthetic model
smoke report, independent of deterministic core CI. It is not a quality benchmark
or a record of user data. Release approval remains separate from these records.
