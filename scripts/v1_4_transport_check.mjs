/** Real fetch cancellation regressions shared by reference and installed clients.
 * The installed-artifact runner selects the generated starter via the env var.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { createServer } from "node:http";
import { spawn } from "node:child_process";
import { dirname, join } from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { pathToFileURL } from "node:url";

const starter = process.env.ALETHEIA_TEST_TRANSPORT;
const clients = starter
  ? [["installed agent", (await import(pathToFileURL(starter))).agentClient, "/v1/remember"]]
  : [["read", (await import("../contracts/typescript/dist/read-client.js")).readClient, "/v1/context-pack"],
     ["review", (await import("../contracts/typescript/dist/review-client.js")).reviewClient, "/v1/candidates/test/promote"]];

for (const [name, createClient, postPath] of clients) {
  for (const method of ["GET", "POST"]) {
    for (const stage of ["headers", "body"]) {
      for (const cancellation of ["deadline", "caller"]) {
        test(`${name}: ${method} ${cancellation} while ${stage} stalled, with GC`, { timeout: 6000 }, async t => {
          assert.equal(typeof global.gc, "function", "Run with --expose-gc; this regression requires real GC");
          let started, count = 0;
          const received = new Promise(resolve => { started = resolve; });
          const server = createServer((request, response) => {
            count++; request.resume();
            if (stage === "body") {
              response.writeHead(200, { "Content-Type": "application/json" });
              response.write('{"data":');
            }
            started(); // Deliberately never complete the response.
          });
          await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
          t.after(async () => {
            const closed = new Promise(resolve => server.close(resolve));
            server.closeAllConnections(); await closed;
          });
          const client = createClient(`http://127.0.0.1:${server.address().port}`, "synthetic", cancellation === "deadline" ? 700 : 20_000);
          const controller = new AbortController();
          const expected = cancellation === "deadline" ? "Request timed out" : "Caller cancelled";
          const request = client[method](method === "GET" ? "/v1/auth/me" : postPath,
            { signal: controller.signal, ...(method === "POST" ? { body: { synthetic: true } } : {}) });
          // A fixture watchdog is a test failure, never evidence of cancellation.
          let watchdog;
          const bounded = Promise.race([request, new Promise((_, reject) => {
            watchdog = setTimeout(() => reject(new Error("Cancellation watchdog expired")), 3000);
          })]);
          t.after(() => clearTimeout(watchdog));
          const rejected = assert.rejects(bounded, error => error instanceof Error && error.message === expected);
          await Promise.race([received, request.then(() => assert.fail("Incomplete response finished"))]);
          // Yield before collecting so fetch has begun consuming the body.
          for (let i = 0; i < 3; i++) { await delay(40); global.gc(); }
          if (cancellation === "caller") controller.abort(new Error(expected));
          await rejected;
          assert.equal(count, 1, "Cancellation must not retry an uncertain operation");
        });
      }
    }
  }
  test(`${name}: already-cancelled caller sends no request`, async t => {
    let sent = 0;
    t.mock.method(globalThis, "fetch", async (_request, options) => {
      options.signal.throwIfAborted(); sent++; return Response.json({ data: {} });
    });
    const controller = new AbortController(); controller.abort(new Error("Already cancelled"));
    await assert.rejects(createClient("http://fixture.invalid", "synthetic").GET("/v1/auth/me", { signal: controller.signal }), /Already cancelled/);
    assert.equal(sent, 0);
  });
}

if (starter) {
  test("installed agent CLI obeys its default 10-second body deadline under GC", { timeout: 16_000 }, async t => {
    let count = 0;
    const server = createServer((request, response) => {
      count++; request.resume();
      response.writeHead(200, { "Content-Type": "application/json" });
      response.write('{"data":');
    });
    await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
    const child = spawn(process.execPath, ["--expose-gc", "--import",
      "data:text/javascript,setInterval(() => global.gc(), 100).unref();",
      join(dirname(starter), "agent.js"), "read"], {
      env: { ALETHEIA_URL: `http://127.0.0.1:${server.address().port}`, ALETHEIA_AGENT_TOKEN: "synthetic" },
      stdio: ["ignore", "pipe", "pipe"],
    });
    let stderr = "", expired = false;
    child.stderr.on("data", data => { stderr += data; });
    const watchdog = setTimeout(() => { expired = true; child.kill("SIGTERM"); }, 13_000);
    t.after(async () => {
      clearTimeout(watchdog); child.kill("SIGTERM");
      const closed = new Promise(resolve => server.close(resolve));
      server.closeAllConnections(); await closed;
    });
    const code = await new Promise((resolve, reject) => { child.on("close", resolve); child.on("error", reject); });
    assert.equal(expired, false, "The fixture watchdog must not be what stops the agent");
    assert.equal(code, 1);
    assert.match(stderr, /Request timed out/);
    assert.equal(count, 1, "No retry or memory operation after failed discovery");
  });
}
