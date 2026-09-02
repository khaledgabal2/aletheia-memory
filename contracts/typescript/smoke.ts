// Phase 0 proves generator/transport wiring, not endpoint-specific domain typing.
import assert from "node:assert/strict";
import createClient from "openapi-fetch";
import type { paths } from "./generated/baseline.js";

const baseUrl = process.env.ALETHEIA_TEST_URL;
const token = process.env.ALETHEIA_TEST_TOKEN;
assert(baseUrl && token, "Run through scripts/v1_4_phase0.py --typescript");
const client = createClient<paths>({ baseUrl, headers: { Authorization: `Bearer ${token}` } });
const version = await client.GET("/v1/version", { signal: AbortSignal.timeout(5000) });
assert.equal(version.response.status, 200);
assert(version.data?.request_id);
const retrieved = await client.POST("/v1/retrieve", {
  body: { namespace: "user/phase0-demo", query: "architecture", mode: "lexical" },
  signal: AbortSignal.timeout(5000),
});
assert.equal(retrieved.response.status, 200);
assert.deepEqual(retrieved.data?.data, []);
console.log("Generated baseline client: discovery and empty lexical read passed; domain data remains unknown until G2.");
