# Memory contract tooling

Private, development-only tooling owned by Memory. No Desktop checkout or code
is used. Nothing here is installed by `pip install aletheia-memory`.

From the Memory checkout, after installing `.[dev]`:

```sh
npm ci --prefix contracts/typescript --ignore-scripts --no-audit --no-fund
npm run generate --prefix contracts/typescript
python -m scripts.v1_4_discovery_contract --output contracts/typescript/generated/discovery.json
npm run generate:discovery --prefix contracts/typescript
python -m scripts.v1_4_read_contract --output contracts/typescript/generated/read.json
npm run generate:read --prefix contracts/typescript
python -m scripts.v1_4_review_contract --output contracts/typescript/generated/review.json
npm run generate:review --prefix contracts/typescript
python -m scripts.v1_4_agent_contract --output contracts/typescript/generated/onboarding.json
npm run generate:onboarding --prefix contracts/typescript
npm run check --prefix contracts/typescript
npm run build --prefix contracts/typescript
python scripts/v1_4_phase0.py --typescript
python -m scripts.v1_4_discovery_contract --typescript
python -m scripts.v1_4_read_contract --typescript
python -m scripts.v1_4_review_contract --typescript
python -m scripts.v1_4_agent_contract --typescript
npm test --prefix contracts/typescript
```

Tested with Node 26.0.0. Tool versions are pinned in package.json and package-lock.json.
The Python harness binds a fresh loopback service with a disposable database and
passes temporary credentials only through the child process environment. It
always shuts down the service. No existing Memory database is opened.

Phase 0 uses the selected paths extracted from the actual 1.3.1 HTTP OpenAPI
envelope. Generation/compilation and a real transport call can already work,
but domain payload types remain `unknown`. **This is not G2 conformance.**
Path/query parameters and endpoint-specific success/error schemas will be
generated from the current authoritative registry as those operations are
implemented. Do not add handwritten payload casts to conceal missing schemas.

Generated declarations and build output are ignored. Generation starts from
the committed fixture and uses only the locked local generator; it does not
download schemas or contact the live user's service. CI uses `npm ci` and runs
the same Memory-owned local-service harness.

Phase 1 additionally captures and strictly validates the six current discovery
operations before generation. `discovery.ts` exercises software/schema versions,
principal identity, permission metadata and errors with generated domain types.
Phase 2 implements and advertises `memory-read-v1` on the development branch;
Phase 5 adds the candidate-first `agent-onboarding-v1` profile. The canonical read schema is captured
from the running Memory service. Its generated request defaults remain optional
(`--default-non-nullable false`); no handwritten payload substitutes are used.
See [read contract](../../docs/v1_4_0_read_contract.md) for scope, limits and redaction.

## Actual browser check

After generation/build above:

```sh
python -m scripts.v1_4_read_contract --browser
```

Open the printed loopback URL and select **Run browser checks**. This starts a
Memory-owned page and fixed same-origin proxy with a disposable database and
synthetic credentials. The page checks actual authenticated reads, cache and
correlation headers, privacy changes, revocation, cancellation, reconnect and
absence of domain writes. **Connect demo**, **Narrow demo privacy**, **Revoke demo
credentials** and **Disconnect** exercise the live poller and cache clearing.
The Node tests additionally cover stalled bodies, background/offline lifecycle,
non-overlap, late results, changed access during a request and bounded retries.
The shared `scripts/v1_4_transport_check.mjs` suite exercises read and review
GET/POST deadlines and caller cancellation during stalled headers and bodies,
with forced garbage collection and assertions that uncertain calls are not
retried. Installed wheel/sdist checks run the same nine tests against the
generated starter's `transport.ts`, plus an actual agent subprocess check that
must stop at its default 10-second deadline without a fixture watchdog kill.

The fixture is a development test harness, not a deployment proxy or credential
provisioning API. Do not point it at a real database. Stop it with Ctrl-C; its
database and credentials are discarded. No token is written to browser storage.
The source distribution includes this tooling; the Python wheel has no Node
runtime dependency. Generate the packaged TypeScript starter with `aletheia examples create --type typescript-agent --output ts-demo`; its Node toolchain is optional.

Reverse compatibility is a separate installed-service check:

```sh
python -m pip install --no-deps --target .legacy-1.3.1 aletheia-memory==1.3.1
python scripts/v1_4_compatibility_check.py --legacy-package .legacy-1.3.1
```

This test starts only the downloaded 1.3.1 service in an isolated subprocess,
checks its source hashes, and uses the current SDK as the consumer. It does not
substitute the current service with a mocked version string.

## Governed review

Phase 4 adds `memory-review-v1`. Generate before compiling all clients:

```sh
python -m scripts.v1_4_review_contract --output contracts/typescript/generated/review.json
npm run generate:review --prefix contracts/typescript
npm run check --prefix contracts/typescript
npm run build --prefix contracts/typescript
python -m scripts.v1_4_review_contract --typescript
python -m scripts.v1_4_migration_check --legacy-package .legacy-1.3.1
python -m scripts.v1_4_review_contract --browser
```

The browser command serves a separate disposable same-origin page. Select
**Run governed review checks** to inspect two synthetic candidates, reject one,
prove the earlier approval is stale, make a new explicit test decision, promote,
replay and verify that revocation denies replay. This does not exercise any user
database. No key is generated or write retried automatically by `Reviewer`.
Keep the same operation key and complete payload after an uncertain response;
a 412 requires a fresh inspection and new explicit decision. Read the
[contract](../../docs/v1_4_0_review_contract.md) for key retention, cursor bounds,
legacy differences and migration requirements.
