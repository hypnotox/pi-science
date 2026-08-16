import { EventEmitter } from "node:events";
import { readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  appendResponseChunk,
  BridgeError,
  invokeAdapter,
  MAX_EXPRESSION_BYTES,
  MAX_RESPONSE_BYTES,
} from "../src/bridge.js";

const node = process.execPath;
const script = (body: string) => ["-e", body];
const leakedPids: number[] = [];

const pause = (milliseconds: number) =>
  new Promise<void>((resolve) => setTimeout(resolve, milliseconds));

async function recordedDescendant(): Promise<{
  args: string[];
  pidFile: string;
}> {
  const pidFile = join(
    tmpdir(),
    `pi-science-bridge-descendant-${process.pid}-${Date.now()}-${Math.random()}`,
  );
  return {
    pidFile,
    args: script(`
      const fs=require("fs"),cp=require("child_process");
      const child=cp.spawn(process.execPath,["-e",\`process.on("SIGTERM",()=>{});setInterval(()=>{},1000)\`],{stdio:"ignore"});
      fs.writeFileSync(${JSON.stringify(pidFile)},String(child.pid));
      process.on("SIGTERM",()=>{});setInterval(()=>{},1000);
    `),
  };
}

async function readRecordedPid(pidFile: string): Promise<number> {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    try {
      const pid = Number((await readFile(pidFile, "utf8")).trim());
      if (Number.isSafeInteger(pid) && pid > 0) {
        leakedPids.push(pid);
        return pid;
      }
    } catch {
      // The parent has not recorded its resistant descendant yet.
    }
    await pause(10);
  }
  throw new Error("resistant descendant PID was not recorded");
}

async function expectGone(pid: number): Promise<void> {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    try {
      process.kill(pid, 0);
    } catch (error: unknown) {
      if ((error as NodeJS.ErrnoException).code === "ESRCH") return;
      throw error;
    }
    await pause(10);
  }
  throw new Error(`resistant descendant ${pid} remained alive after cleanup`);
}

afterEach(async () => {
  for (const pid of leakedPids.splice(0)) {
    try {
      process.kill(pid, "SIGKILL");
    } catch {
      // The operation already cleaned up the descendant.
    }
    await expectGone(pid);
  }
});
const success = {
  status: "success",
  interpretation: { normalized_sympy: "x", normalized_latex: "x" },
  operation_counts: {
    additions: 0,
    subtractions: 0,
    multiplications: 0,
    divisions: 0,
    powers: 0,
  },
  abstract_work: 0,
};
const responder = (result: unknown = success) =>
  script(
    `process.stdin.resume();process.stdin.on("end",()=>process.stdout.write(${JSON.stringify(
      JSON.stringify({ version: 1, result }),
    )}))`,
  );

function request(expression = "x") {
  return { syntax: "sympy" as const, expression };
}

async function kind(promise: Promise<unknown>, expected: BridgeError["kind"]) {
  await expect(promise).rejects.toMatchObject({
    kind: expected,
  } satisfies Partial<BridgeError>);
}

describe("private formula bridge", () => {
  it("round trips the actual adapter for success and analysis failure", async () => {
    const adapter = fileURLToPath(
      new URL("../bridge/formula_adapter.py", import.meta.url),
    );
    const args = ["run", "--locked", "python", adapter];
    await expect(
      invokeAdapter("uv", args, request("x + 1")),
    ).resolves.toMatchObject({
      status: "success",
      abstract_work: 1,
    });
    await expect(
      invokeAdapter("uv", args, request("x(")),
    ).resolves.toMatchObject({
      status: "failure",
      error: { code: "malformed_syntax" },
    });
  });

  it("strictly rejects malformed envelopes and result shapes", async () => {
    const outputs = [
      "no",
      JSON.stringify(null),
      JSON.stringify([]),
      JSON.stringify({ version: 2, result: success }),
      JSON.stringify({ version: 1, result: success, extra: true }),
      JSON.stringify({ version: 1, result: null }),
      JSON.stringify({ version: 1, result: [] }),
      JSON.stringify({ version: 1, result: { status: "success" } }),
      JSON.stringify({
        version: 1,
        result: { ...success, unexpected: true },
      }),
    ];
    for (const output of outputs) {
      const promise = invokeAdapter(
        node,
        script(`process.stdout.write(${JSON.stringify(output)})`),
        request(),
      );
      await kind(promise, output === "no" ? "malformed-output" : "protocol");
    }
  });

  it("bounds expressions by UTF-8 bytes while permitting empty and boundary input", async () => {
    await expect(
      invokeAdapter(node, responder(), request("")),
    ).resolves.toEqual(success);
    const boundary = "é".repeat(MAX_EXPRESSION_BYTES / 2);
    await expect(
      invokeAdapter(node, responder(), request(boundary)),
    ).resolves.toEqual(success);
    await kind(
      invokeAdapter(node, responder(), request(`${boundary}é`)),
      "protocol",
    );
  });

  it("consumes and bounds large stderr on a failed child", async () => {
    const promise = invokeAdapter(
      node,
      script(
        'process.stderr.write("diagnostic".repeat(200000),()=>process.exit(2))',
      ),
      request(),
    );
    await expect(promise).rejects.toMatchObject({ kind: "process" });
    await expect(promise).rejects.toHaveProperty(
      "message",
      expect.stringMatching(/^formula adapter exited unsuccessfully/),
    );
  });

  it("bounds retained output and cleans a resistant high-volume producer", async () => {
    const retained = appendResponseChunk(
      Buffer.from("prefix"),
      Buffer.alloc(MAX_RESPONSE_BYTES * 4, "x"),
    );
    expect(retained.overflow).toBe(true);
    expect(retained.retained.length).toBe(MAX_RESPONSE_BYTES);

    await kind(
      invokeAdapter(
        node,
        script(`
          process.on("SIGTERM",()=>{});
          const chunk=Buffer.alloc(${MAX_RESPONSE_BYTES},"x");
          const flood=()=>{while(process.stdout.write(chunk)){};process.stdout.once("drain",flood)};
          flood();setInterval(()=>{},1000);
        `),
        request(),
      ),
      "malformed-output",
    );
  });

  it("rejects spawn errors with bounded actionable detail and oversized stdout", async () => {
    let error: BridgeError | undefined;
    try {
      await invokeAdapter("/missing/pi-science-command", [], request());
    } catch (value) {
      error = value as BridgeError;
    }
    expect(error).toBeDefined();
    const detail = error!;
    expect(detail).toMatchObject({ kind: "environment" });
    expect(detail.message).toContain("ENOENT");
    expect(Buffer.byteLength(detail.message)).toBeLessThanOrEqual(4_200);
    await kind(
      invokeAdapter(
        node,
        script(`process.stdout.write("x".repeat(${MAX_RESPONSE_BYTES + 1}))`),
        request(),
      ),
      "malformed-output",
    );
  });

  it("rejects escape-heavy envelopes that exceed the adapter byte bound", async () => {
    await kind(
      invokeAdapter(node, responder(), request("\u0000".repeat(20_000))),
      "protocol",
    );
  });

  it("honors pre-abort and removes recorded SIGTERM-resistant descendants on timeout", async () => {
    const controller = new AbortController();
    controller.abort();
    await kind(
      invokeAdapter(node, responder(), request(), 1_000, controller.signal),
      "cancelled",
    );
    const descendant = await recordedDescendant();
    const promise = invokeAdapter(node, descendant.args, request(), 100);
    const pid = await readRecordedPid(descendant.pidFile);
    try {
      await kind(promise, "timeout");
      await expectGone(pid);
    } finally {
      await rm(descendant.pidFile, { force: true });
    }
  });

  it("observes abort arriving between precheck and listener registration", async () => {
    let aborted = false;
    const raced = {
      get aborted() {
        return aborted;
      },
      addEventListener() {
        aborted = true;
      },
      removeEventListener() {},
    } as unknown as AbortSignal;
    await kind(
      invokeAdapter(
        node,
        script('process.on("SIGTERM",()=>{});setInterval(()=>{},1000)'),
        request(),
        5_000,
        raced,
      ),
      "cancelled",
    );
  });

  it("cancels a running tree and removes its recorded SIGTERM-resistant descendant", async () => {
    const controller = new AbortController();
    const descendant = await recordedDescendant();
    const promise = invokeAdapter(
      node,
      descendant.args,
      request(),
      5_000,
      controller.signal,
    );
    const pid = await readRecordedPid(descendant.pidFile);
    try {
      controller.abort();
      await kind(promise, "cancelled");
      await expectGone(pid);
    } finally {
      await rm(descendant.pidFile, { force: true });
    }
  });

  it("fails closed when stdin reports a non-cleanup error", async () => {
    const stdin = new EventEmitter() as NodeJS.WritableStream;
    const child = Object.assign(new EventEmitter(), {
      pid: 42,
      stdin,
      stdout: new EventEmitter(),
      stderr: new EventEmitter(),
    });
    let terminated = false;
    vi.resetModules();
    vi.doMock("../src/process.js", () => ({
      spawnIsolated: () => child,
      terminateTree: () => {
        terminated = true;
        setImmediate(() => child.emit("close", null));
      },
    }));
    try {
      const { invokeAdapter: invokeWithFault } =
        await import("../src/bridge.js");
      stdin.end = () => {
        stdin.emit("error", new Error("stdin transport failed"));
        return stdin;
      };
      await expect(
        invokeWithFault(node, [], request(), 50),
      ).rejects.toMatchObject({
        kind: "process",
        message: expect.stringContaining("stdin transport failed"),
      });
      expect(terminated).toBe(true);
    } finally {
      vi.doUnmock("../src/process.js");
      vi.resetModules();
    }
  });
});
