import createClient from "openapi-fetch";
import type { paths } from "./schema.js";

/** One deadline covers headers and body; caller cancellation stays connected.
 * Never retry a write automatically: its outcome may be unknown after abort.
 */
export function agentClient(baseUrl: string, token: string, timeoutMs = 10_000) {
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
        // Keep the controller's signal directly attached to fetch, including
        // while buffering the body (also under Node garbage collection).
        const response = await fetch(request, { headers, signal: controller.signal, cache: "no-store" });
        const body = await response.arrayBuffer();
        if (!response.ok) throw Error(`Memory request failed (${response.status}); inspect scope or the pending operation before retrying.`);
        return new Response(body, { status: response.status, headers: response.headers });
      } finally {
        clearTimeout(timer);
        request.signal.removeEventListener("abort", abort);
      }
    },
  });
}
