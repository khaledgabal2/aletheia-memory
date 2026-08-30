import createClient from "openapi-fetch";
import type { paths, components } from "./generated/read.js";

type Principal = components["schemas"]["CurrentPrincipal"];
export class ReadError extends Error {
  constructor(message: string, public status = 0, public retryAfterMs?: number) { super(message); }
  get transient() { return this.status === 0 || this.status === 429 || this.status >= 500; }
}

export function scopeKey(principal: Principal): string {
  return JSON.stringify([principal.service_identity, principal.authentication_mode, principal.principal,
    [...principal.capabilities].sort(), [...principal.namespace_grants].sort(), principal.privacy_ceiling, principal.expires_at]);
}

export function readClient(baseUrl: string, token: string, timeoutMs = 10_000) {
  return createClient<paths>({ baseUrl, headers: { Authorization: `Bearer ${token}`, "X-Aletheia-Contract": "memory-read-v1" },
    fetch: async (request: Request) => {
      const controller = new AbortController();
      const abort = () => controller.abort(request.signal.reason);
      request.signal.addEventListener("abort", abort, { once: true });
      if (request.signal.aborted) abort();
      const timer = setTimeout(() => controller.abort(new ReadError("Request timed out")), timeoutMs);
      const headers = new Headers(request.headers);
      headers.set("X-Request-ID", crypto.randomUUID());
      try {
        const response = await fetch(new Request(request, { headers, signal: controller.signal, cache: "no-store" }));
        if (!response.ok) {
          const hint = response.headers.get("Retry-After");
          const seconds = hint === null ? NaN : Number(hint);
          const retry = Number.isFinite(seconds) ? Math.max(0, seconds * 1000) : hint ? Math.max(0, Date.parse(hint) - Date.now()) : undefined;
          throw new ReadError(`Memory request failed (${response.status})`, response.status, retry);
        }
        // Keep the deadline and cancellation active while the body is arriving.
        const body = await response.arrayBuffer();
        return new Response(body, { status: response.status, statusText: response.statusText, headers: response.headers });
      } finally {
        clearTimeout(timer);
        request.signal.removeEventListener("abort", abort);
      }
    },
  });
}

export class ScopedReader {
  readonly client: ReturnType<typeof readClient>;
  private scope: string | undefined;
  constructor(baseUrl: string, token: string, private clear: () => void, timeoutMs = 10_000) {
    this.client = readClient(baseUrl, token, timeoutMs);
  }
  reset() { this.scope = undefined; this.clear(); }
  private async principal(signal: AbortSignal) {
    const result = await this.client.GET("/v1/auth/me", { signal });
    if (!result.data) throw new ReadError("Principal data unavailable", 502);
    if (!result.data.data.supported_profiles.includes("memory-read-v1")) {
      this.reset();
      throw new ReadError("This service does not support memory-read-v1", 426);
    }
    return result.data.data;
  }
  async read<T>(operation: (client: ReturnType<typeof readClient>, signal: AbortSignal) => Promise<T>, signal: AbortSignal): Promise<T> {
    try {
      const before = scopeKey(await this.principal(signal));
      if (before !== this.scope) { this.clear(); this.scope = before; }
      const value = await operation(this.client, signal);
      const after = scopeKey(await this.principal(signal));
      if (signal.aborted) throw signal.reason;
      if (after !== before || this.scope !== before) {
        this.reset();
        throw new ReadError("Access changed during the request; refresh required", 409);
      }
      return value;
    } catch (error) {
      if (error instanceof ReadError && [401, 403, 409].includes(error.status)) this.reset();
      throw error;
    }
  }
}

type Schedule = (callback: () => void, delay: number) => () => void;
export type PollOptions<T> = {
  load: (signal: AbortSignal) => Promise<T>;
  data: (value: T) => void;
  clear: () => void;
  error: (error: unknown) => void;
  visible?: () => boolean;
  online?: () => boolean;
  schedule?: Schedule;
  random?: () => number;
  intervalMs?: number;
};

export class ReadPoller<T> {
  private cancelTimer?: () => void;
  private controller?: AbortController;
  private failures = 0;
  private running = false;
  private generation = 0;
  private pendingRefresh = false;
  private readonly schedule: Schedule;
  private readonly ready: () => boolean;
  private readonly wake = () => this.refresh();
  constructor(private options: PollOptions<T>) {
    this.schedule = options.schedule ?? ((callback, delay) => { const id = setTimeout(callback, delay); return () => clearTimeout(id); });
    this.ready = () => (options.visible?.() ?? (typeof document === "undefined" || document.visibilityState === "visible"))
      && (options.online?.() ?? (typeof navigator === "undefined" || navigator.onLine !== false));
  }
  start() {
    if (this.running) return;
    this.running = true;
    if (typeof document !== "undefined") document.addEventListener("visibilitychange", this.wake);
    if (typeof window !== "undefined") { window.addEventListener("online", this.wake); window.addEventListener("offline", this.wake); }
    this.refresh();
  }
  stop() {
    this.running = false; this.generation++; this.pendingRefresh = false;
    this.cancelTimer?.(); this.cancelTimer = undefined;
    this.controller?.abort();
    this.options.clear();
    if (typeof document !== "undefined") document.removeEventListener("visibilitychange", this.wake);
    if (typeof window !== "undefined") { window.removeEventListener("online", this.wake); window.removeEventListener("offline", this.wake); }
  }
  refresh() {
    this.cancelTimer?.(); this.cancelTimer = undefined;
    if (!this.running) return;
    if (!this.ready()) {
      this.generation++; this.controller?.abort(); this.options.clear();
      return;
    }
    if (this.controller) { this.pendingRefresh = true; return; }
    void this.poll();
  }
  private async poll() {
    if (!this.running || !this.ready() || this.controller) return;
    const generation = this.generation;
    const controller = new AbortController(); this.controller = controller;
    let delay = this.options.intervalMs ?? 5000;
    let permanent = false;
    let failed = false;
    try {
      const value = await this.options.load(controller.signal);
      if (controller.signal.aborted || generation !== this.generation || !this.running) return;
      this.failures = 0; this.options.data(value);
    } catch (error) {
      if (controller.signal.aborted || generation !== this.generation || !this.running) return;
      this.options.clear(); this.options.error(error);
      failed = true;
      permanent = error instanceof ReadError && !error.transient;
      this.failures++;
      const backoff = Math.min(60000, (this.options.intervalMs ?? 5000) * 2 ** Math.min(this.failures, 8));
      delay = Math.min(60000, Math.max(backoff * (0.8 + (this.options.random?.() ?? Math.random()) * 0.2),
        error instanceof ReadError && Number.isFinite(error.retryAfterMs) ? error.retryAfterMs! : 0));
    } finally {
      this.controller = undefined;
      if (permanent) this.stop();
      if (this.running && this.ready()) {
        const wait = this.pendingRefresh && !failed ? 0 : delay; this.pendingRefresh = false;
        this.cancelTimer = this.schedule(() => { this.cancelTimer = undefined; void this.poll(); }, wait);
      }
    }
  }
}
