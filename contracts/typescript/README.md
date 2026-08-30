# Memory contract-toolchain baseline

Private, development-only tooling owned by Memory. No Desktop checkout or code
is used. Nothing here is installed by `pip install aletheia-memory`.

From the Memory checkout, after installing `.[dev]`:

```sh
npm ci --prefix contracts/typescript --ignore-scripts --no-audit --no-fund
npm run generate --prefix contracts/typescript
npm run check --prefix contracts/typescript
npm run build --prefix contracts/typescript
python scripts/v1_4_phase0.py --typescript
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
