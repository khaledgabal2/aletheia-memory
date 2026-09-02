import createClient from "openapi-fetch";
import type { paths, components } from "./generated/review.js";

export type ReviewCandidate = components["schemas"]["ReviewCandidate"];
export type ReviewOutcome = components["schemas"]["ReviewOutcome"];
export class ReviewError extends Error {
  constructor(message: string, public status: number, public code: string) { super(message); }
}

/** No automatic write retry, revision refresh, key generation, or forced decision. */
export function reviewClient(baseUrl: string, token: string, timeoutMs = 10_000) {
  return createClient<paths>({ baseUrl, headers: { Authorization: `Bearer ${token}` },
    fetch: async (request: Request) => {
      const controller = new AbortController();
      const abort = () => controller.abort(request.signal.reason);
      request.signal.addEventListener("abort", abort, { once: true });
      if (request.signal.aborted) abort();
      const timer = setTimeout(() => controller.abort(new Error("Request timed out")), timeoutMs);
      const headers = new Headers(request.headers);
      headers.set("X-Request-ID", crypto.randomUUID());
      try {
        // Pass the live signal directly; an intermediate Request can lose its
        // abort forwarding during body transfer under Node garbage collection.
        const response = await fetch(request, { headers, signal: controller.signal, cache: "no-store" });
        const body = await response.arrayBuffer();
        if (!response.ok) {
          // Error JSON is untrusted; surface only the documented code and status.
          let code = "unknown_error";
          try { const value = JSON.parse(new TextDecoder().decode(body));
            if (typeof value?.error?.code === "string") code = value.error.code;
          } catch { /* A failed intermediary may return non-JSON. */ }
          throw new ReviewError(`Memory review failed (${response.status}, ${code})`, response.status, code);
        }
        return new Response(body, { status: response.status, headers: response.headers });
      } finally {
        clearTimeout(timer);
        request.signal.removeEventListener("abort", abort);
      }
    },
  });
}

export class Reviewer {
  readonly client: ReturnType<typeof reviewClient>;
  private identity?: string;
  constructor(baseUrl: string, token: string, private clear: () => void = () => {}) {
    this.client = reviewClient(baseUrl, token);
  }
  reset() { this.identity = undefined; this.clear(); }
  async connect(signal?: AbortSignal) {
    try {
      const response = await this.client.GET("/v1/auth/me", { signal });
      if (!response.data?.data.supported_profiles.includes("memory-review-v1")) {
        throw new ReviewError("This service does not support memory-review-v1", 426, "unsupported_feature");
      }
      const p = response.data.data;
      const identity = JSON.stringify([p.service_identity, p.authentication_mode, p.principal,
        [...p.capabilities].sort(), [...p.namespace_grants].sort(), p.privacy_ceiling, p.expires_at]);
      if (identity !== this.identity) { this.clear(); this.identity = identity; }
      return p;
    } catch (error) { this.reset(); throw error; }
  }
  async inspect(candidateId: string, signal?: AbortSignal): Promise<ReviewCandidate> {
    await this.connect(signal);
    const identity = this.identity;
    try {
      const response = await this.client.GET("/v1/candidates/{candidate_id}", { signal,
        params: { path: { candidate_id: candidateId }, header: { "X-Aletheia-Contract": "memory-review-v1" } } });
      if (!response.data) throw new ReviewError("Candidate unavailable", 502, "missing_data");
      await this.connect(signal);
      if (identity !== this.identity) throw new ReviewError("Access changed; inspect again", 409, "access_changed");
      return response.data.data;
    } catch (error) { this.reset(); throw error; }
  }
  async decide(candidateId: string, action: "promote" | "reject", reason: string,
    expectedRevision: string, idempotencyKey: string, signal?: AbortSignal): Promise<ReviewOutcome> {
    await this.connect(signal);
    try {
      const path = action === "promote" ? "/v1/candidates/{candidate_id}/promote" : "/v1/candidates/{candidate_id}/reject";
      const response = await this.client.POST(path, { signal,
        params: { path: { candidate_id: candidateId }, header: {
          "X-Aletheia-Contract": "memory-review-v1", "Idempotency-Key": idempotencyKey } },
        body: { reason, expected_revision: expectedRevision } });
      if (!response.data) throw new ReviewError("Outcome unknown; retain the same key and payload", 502, "missing_data");
      return response.data.data;
    } catch (error) { this.reset(); throw error; }
  }
}
