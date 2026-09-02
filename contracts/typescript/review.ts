import assert from "node:assert/strict";
import { Reviewer, ReviewError } from "./review-client.js";

const url = process.env.ALETHEIA_TEST_URL, token = process.env.ALETHEIA_TEST_TOKEN;
const firstId = process.env.ALETHEIA_TEST_FIRST, secondId = process.env.ALETHEIA_TEST_SECOND;
assert(url && token && firstId && secondId);
const reviewer = new Reviewer(url, token);
await reviewer.connect();
const page = await reviewer.client.GET("/v1/candidates", { params: {
  query: { namespace: "user/phase0-demo", limit: 1 }, header: { "X-Aletheia-Contract": "memory-review-v1" } } });
assert(page.data?.pagination.next_cursor && page.data.data.length === 1);
const first = await reviewer.inspect(firstId), second = await reviewer.inspect(secondId);
const rejected = await reviewer.decide(second.id, "reject", "Explicit generated-client refusal", second.revision, "typed-reject");
assert.equal(rejected.claim_id, null);
await assert.rejects(reviewer.decide(first.id, "promote", "Stale decision", first.revision, "typed-stale"),
  error => error instanceof ReviewError && error.status === 412 && error.code === "stale_revision");
// A new inspection and an explicit new decision are required after rejection.
const refreshed = await reviewer.inspect(first.id);
const reason = "New explicit generated-client approval", key = "typed-promote";
const promoted = await reviewer.decide(first.id, "promote", reason, refreshed.revision, key);
assert(promoted.claim_id);
assert.deepEqual(await reviewer.decide(first.id, "promote", reason, refreshed.revision, key), promoted);
const audit = await reviewer.client.GET("/v1/audit/{target_type}/{target_id}", { params: {
  path: { target_type: "claim", target_id: promoted.claim_id } } });
assert(audit.data?.data.target_type === "claim" && audit.data.data.claim.id === promoted.claim_id);
console.log("Generated review client: principal, keyset page, inspect, reject, stale refusal, new decision, promotion, replay and audit passed.");
