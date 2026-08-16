import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import {
  BridgeError,
  invokeAdapter,
  MAX_EXPRESSION_BYTES,
  MAX_RESPONSE_BYTES,
} from "../src/bridge.js";

const node = process.execPath;
const script = (body: string) => ["-e", body];
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

  it("rejects spawn errors and oversized stdout", async () => {
    await kind(
      invokeAdapter("/missing/pi-science-command", [], request()),
      "environment",
    );
    await kind(
      invokeAdapter(
        node,
        script(`process.stdout.write("x".repeat(${MAX_RESPONSE_BYTES + 1}))`),
        request(),
      ),
      "malformed-output",
    );
  });

  it("honors pre-abort and kills SIGTERM-resistant children on timeout", async () => {
    const controller = new AbortController();
    controller.abort();
    await kind(
      invokeAdapter(node, responder(), request(), 1_000, controller.signal),
      "cancelled",
    );
    await kind(
      invokeAdapter(
        node,
        script('process.on("SIGTERM",()=>{});setInterval(()=>{},1000)'),
        request(),
        20,
      ),
      "timeout",
    );
  });

  it("cancels a running SIGTERM-resistant child", async () => {
    const controller = new AbortController();
    const promise = invokeAdapter(
      node,
      script('process.on("SIGTERM",()=>{});setInterval(()=>{},1000)'),
      request(),
      5_000,
      controller.signal,
    );
    setTimeout(() => controller.abort(), 20);
    await kind(promise, "cancelled");
  });
});
