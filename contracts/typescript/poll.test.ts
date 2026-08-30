import assert from "node:assert/strict";
import test from "node:test";
import { createServer } from "node:http";
import { ReadError, ReadPoller, readClient, ScopedReader } from "./read-client.js";

const flush = async () => { for (let i = 0; i < 10; i++) await Promise.resolve(); };

test("polling never overlaps; stop drops an in-flight result", async () => {
  let finish!: (value: string) => void;
  let calls = 0, output = "", signal!: AbortSignal;
  const poller = new ReadPoller({ load: current => { calls++; signal = current; return new Promise<string>(resolve => { finish = resolve; }); },
    data: value => { output = value; }, clear: () => { output = ""; }, error: () => {} });
  poller.start(); poller.refresh(); poller.refresh();
  assert.equal(calls, 1);
  poller.stop(); assert(signal.aborted);
  finish("stale"); await flush();
  assert.equal(output, ""); assert.equal(calls, 1);
});

test("background/offline pause and reconnect; obsolete response never renders", async () => {
  let visible = false, online = true, calls = 0, output = "";
  let finish!: (value: number) => void;
  const timers: (() => void)[] = [];
  const poller = new ReadPoller({ load: () => { calls++; return new Promise<number>(resolve => { finish = resolve; }); },
    visible: () => visible, online: () => online, data: value => { output = String(value); }, clear: () => { output = ""; }, error: () => {},
    schedule: callback => { timers.push(callback); return () => {}; } });
  poller.start(); assert.equal(calls, 0);
  visible = true; poller.refresh(); assert.equal(calls, 1);
  online = false; poller.refresh(); finish(1); await flush(); assert.equal(output, "");
  online = true; poller.refresh(); assert.equal(calls, 2);
  finish(2); await flush(); assert.equal(output, "2");
  poller.stop();
});

test("bounded backoff honors retry hints; authorization and validation stop polling", async () => {
  const timers: { callback: () => void; delay: number }[] = [];
  let status = 429, calls = 0;
  const poller = new ReadPoller({ load: async () => { calls++; throw new ReadError("fixture", status, 20000); },
    data: () => assert.fail(), clear: () => {}, error: () => {}, random: () => 1,
    schedule: (callback, delay) => { timers.push({ callback, delay }); return () => {}; } });
  poller.start(); await flush(); assert.equal(timers[0]?.delay, 20000);
  for (let i = 0; i < 6; i++) { timers.at(-1)!.callback(); await flush(); assert(timers.at(-1)!.delay <= 60000); }
  status = 403; const count = timers.length; timers.at(-1)!.callback(); await flush();
  assert.equal(timers.length, count);
  const stoppedAt = calls; poller.refresh(); await flush(); assert.equal(calls, stoppedAt);
  assert.equal(new ReadError("bad input", 400).transient, false);
});

test("deadline includes a stalled response body", async () => {
  let started!: () => void;
  const headersSent = new Promise<void>(resolve => { started = resolve; });
  const server = createServer((_request, response) => {
    response.writeHead(200, { "Content-Type": "application/json" });
    response.write('{"data":'); started(); // Deliberately never complete the body.
  });
  await new Promise<void>(resolve => server.listen(0, "127.0.0.1", resolve));
  const address = server.address(); assert(address && typeof address !== "string");
  try {
    const request = readClient(`http://127.0.0.1:${address.port}`, "synthetic", 200).GET("/v1/auth/me");
    const rejected = assert.rejects(request);
    await headersSent; await rejected;
  } finally {
    server.closeAllConnections();
    await new Promise<void>(resolve => server.close(() => resolve()));
  }
});

test("scope changes during a request discard its result, and unsupported profiles stop", async t => {
  let ceiling = "personal", profiles = ["memory-read-v1"], cleared = 0;
  t.mock.method(globalThis, "fetch", async () => Response.json({ data: {
    service_identity: "synthetic-service", authentication_mode: "bearer", principal: { id: "synthetic" },
    capabilities: ["memory:read"], namespace_grants: ["user/test"], privacy_ceiling: ceiling, expires_at: null,
    supported_profiles: profiles,
  }, request_id: "synthetic", warnings: [] }));
  const reader = new ScopedReader("http://fixture.invalid", "synthetic", () => { cleared++; });
  const signal = new AbortController().signal;
  await assert.rejects(reader.read(async () => { ceiling = "public"; return "must not render"; }, signal),
    error => error instanceof ReadError && error.status === 409);
  assert(cleared >= 2);
  assert.equal(await reader.read(async () => "fresh scope", signal), "fresh scope");
  profiles = [];
  await assert.rejects(reader.read(async () => assert.fail("unsupported operation ran"), signal),
    error => error instanceof ReadError && error.status === 426);
});
