import assert from "node:assert/strict";
import { ScopedReader } from "./read-client.js";

const url = process.env.ALETHEIA_TEST_URL, token = process.env.ALETHEIA_TEST_TOKEN, claim = process.env.ALETHEIA_TEST_CLAIM;
assert(url && token && claim);
const reader = new ScopedReader(url, token, () => {});
await reader.read(async (client, signal) => {
  const overview = await client.GET("/v1/dashboard/overview", { signal, params: { query: { namespace: "user/phase0-demo" } } });
  assert(overview.data);
  const count: number = overview.data.data.metrics.active_claim_count;
  assert(count > 0);
  assert(overview.data.data.unavailable_sections.includes("candidates"));
  const retrieved = await client.POST("/v1/retrieve", { signal, body: { namespace: "user/phase0-demo", query: "architecture", mode: "lexical", limit: 10 } });
  assert(retrieved.data?.data.some(item => item.claim_id === claim));
  const pack = await client.POST("/v1/context-pack", { signal, body: { namespace: "user/phase0-demo", query: "architecture", retrieval_mode: "lexical", record_usage: false } });
  assert(pack.data?.data.provenance.some(item => item.claim_id === claim));
  const detail = await client.GET("/v1/claims/{claim_id}", { signal, params: { path: { claim_id: claim } } });
  assert(detail.data?.data.evidence_ids.length);
  const explanation = await client.GET("/v1/claims/{claim_id}/explain", { signal, params: { path: { claim_id: claim } } });
  assert(explanation.data?.data.evidence[0]?.content);
  const audit = await client.GET("/v1/audit/{target_type}/{target_id}", { signal, params: { path: { target_type: "claim", target_id: claim } } });
  assert(audit.data?.data.target_type === "claim" && audit.data.data.claim.id === claim);
  return true;
}, new AbortController().signal);
console.log("Generated read client: overview, retrieval, context, claim, explanation, audit and principal isolation passed.");
