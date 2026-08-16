import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const adapter = fileURLToPath(
  new URL("../bridge/formula_adapter.py", import.meta.url),
);

function invoke(input: string) {
  return spawnSync("uv", ["run", "--locked", "python", adapter], {
    input,
    encoding: "utf8",
    maxBuffer: 10_000,
  });
}

describe("formula adapter protocol boundary", () => {
  it.each([
    ["malformed request", "not json"],
    ["incompatible protocol", JSON.stringify({ version: 2, request: {} })],
    ["oversized envelope", "x".repeat(66_561)],
  ])("returns a bounded deterministic error for %s", (_name, input) => {
    const result = invoke(input);
    expect(result.status).toBe(2);
    expect(result.stderr).toBe("");
    expect(Buffer.byteLength(result.stdout)).toBeLessThan(10_000);
    expect(JSON.parse(result.stdout)).toMatchObject({
      version: 1,
      error: { kind: "request" },
    });
  });
});
