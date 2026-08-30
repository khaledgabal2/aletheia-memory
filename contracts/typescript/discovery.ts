import assert from "node:assert/strict";
import createClient from "openapi-fetch";
import type { paths } from "./generated/discovery.js";

const baseUrl = process.env.ALETHEIA_TEST_URL;
const token = process.env.ALETHEIA_TEST_TOKEN;
assert(baseUrl && token, "Run the Memory-owned discovery harness");
const client = createClient<paths>({ baseUrl, headers: { Authorization: `Bearer ${token}` } });
const options = () => ({ signal: AbortSignal.timeout(5000) });
const version = await client.GET("/v1/version", options());
assert.equal(version.response.status, 200);
assert(version.data);
const softwareVersion: string = version.data.data.software_version;
const profiles: string[] = version.data.data.supported_profiles;
assert.equal(softwareVersion, version.data.data.service_version);
assert.deepEqual(profiles, []); // No unimplemented profile is advertised.

const principal = await client.GET("/v1/auth/me", options());
assert(principal.data);
assert.equal(principal.data.data.authentication_mode, "bearer");
assert.equal(principal.data.data.service_identity, version.data.data.service_identity);
assert(principal.data.data.principal?.id);
assert(principal.data.data.capabilities.includes("memory:read"));
assert.deepEqual(principal.data.data.namespace_grants, ["user/phase0-demo"]);
assert.equal(principal.response.headers.get("Cache-Control"), "no-store");

const report = await client.GET("/v1/compatibility/report", {
  ...options(), params: { query: { include_plugins: false, include_runtime: false, include_sdks: false } },
});
assert(report.data);
assert.equal(report.data.data.software_version, softwareVersion);
assert.equal(report.data.data.aletheia_version, report.data.data.schema_version);
assert.equal(report.data.data.python_version, null);
const anonymous = createClient<paths>({ baseUrl });
const denied = await anonymous.GET("/v1/auth/me", options());
assert.equal(denied.response.status, 401);
assert.equal(denied.error?.error.code, "unauthorized");
console.log("Typed discovery: software/schema distinction, principal, permissions, compatibility and errors passed.");
