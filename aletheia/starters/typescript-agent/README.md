# Scoped TypeScript agent

This starter is for the 1.4 development/RC package. It includes declarations
generated from Memory's actual onboarding contract, not handwritten domain types.
Use Node 22 or later (verified toolchain: Node 26.0.0), plus the Python environment
containing the matching Memory build. Node is not required for Memory core.

```sh
npm ci --ignore-scripts --no-audit --no-fund
npm run check
npm run build
python operator_demo.py
```

`npm ci` explicitly downloads the locked development/client packages if they are
not cached. No model or hosted inference service is used. The operator starts a
disposable authenticated loopback service and a separate Node agent process,
shows the candidate and source, and asks for approval. The agent gets only
read/context/candidate-write access; it never receives review credentials.
After explicit approval, lexical context includes evidence and survives restart.
Declining leaves the candidate pending. Database reruns and existing directories
are refused; choose a fresh directory instead of deleting something valuable.

The operator retains an explicit creation key. Neither client retries writes
automatically. If a response is uncertain, inspect the original operation or
retry its same key and complete payload. If review returns 412, refresh and make
a new decision. A changed/redacted creation result returns 409/403; it does not
return an old snapshot. Keys expire after 24 hours, so inspect rather than blindly
recreating an old uncertain operation.

For an already configured service, set `ALETHEIA_URL`, `ALETHEIA_AGENT_TOKEN` and
`ALETHEIA_NAMESPACE` in the process environment without committing them. Then:

```sh
node dist/agent.js capture my-explicit-operation-key
node dist/agent.js read
```

Only use an endpoint you intend to trust with the supplied credential and input.
The disposable operator never forwards credentials to a proxy. Keep agent tokens
out of source control, logs and browser storage. Consult the installed review,
onboarding and migration guides before using a real database. This standalone
example has no Desktop, Relay or published npm SDK dependency.
