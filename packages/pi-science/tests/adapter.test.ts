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
    maxBuffer: 400_000,
  });
}

const systemRequest = {
  syntax: "sympy",
  equations: [
    {
      name: "source",
      expression: "Eq(M[b], Sum(basis(i), (i, 0, n[b] - 1)))",
      domains: { b: { lower: "0", upper: "B - 1" } },
    },
    {
      name: "translated",
      expression: "Eq(L[b], translate(M[b]) + M[b])",
      domains: { b: { lower: "0", upper: "B - 1" } },
    },
  ],
  variables: {
    B: { domain: "positive_integer" },
    N: { domain: "positive_integer" },
    n: { domain: "nonnegative_integer" },
  },
  functions: [],
  primitive_costs: [{ name: "basis", parameters: ["i"], work: "i + 1" }],
  assumptions: [
    {
      name: "population",
      relationship: "Sum(n[b], (b, 0, B - 1)) == N",
    },
  ],
  definitions: [],
  scenarios: [{ name: "fixed_boxes", fixed: { B: 4 }, asymptotic: ["N"] }],
};

describe("formula adapter protocol boundary", () => {
  it.each([
    ["malformed request", "not json"],
    ["incompatible protocol", JSON.stringify({ version: 1, request: {} })],
    [
      "extra request key",
      JSON.stringify({
        version: 2,
        request: { syntax: "sympy", expression: "x", extra: true },
      }),
    ],
    [
      "invalid request type",
      JSON.stringify({
        version: 2,
        request: { syntax: "sympy", expression: 1 },
      }),
    ],
    [
      "duplicate envelope key",
      '{"version":2,"version":2,"request":{"syntax":"sympy","expression":"x"}}',
    ],
    ["oversized envelope", "x".repeat(2_097_153)],
  ])("returns a bounded deterministic error for %s", (_name, input) => {
    const result = invoke(input);
    expect(result.status).toBe(2);
    expect(result.stderr).toBe("");
    expect(Buffer.byteLength(result.stdout)).toBeLessThan(10_000);
    expect(JSON.parse(result.stdout)).toMatchObject({
      version: 2,
      error: { kind: "request" },
    });
  });

  it("bounds serialized output before writing it", () => {
    const code = `
import importlib.util, sys
spec = importlib.util.spec_from_file_location("formula_adapter", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
print(module._encoded({"result": "x" * 262401}) is None)
`;
    const result = spawnSync(
      "uv",
      ["run", "--locked", "python", "-c", code, adapter],
      { encoding: "utf8" },
    );
    expect(result.status).toBe(0);
    expect(result.stderr).toBe("");
    expect(result.stdout.trim()).toBe("True");
  });

  it("round trips a complete equation-system request through the real adapter", () => {
    const result = invoke(
      JSON.stringify({ version: 2, request: systemRequest }),
    );
    expect(result.status).toBe(0);
    expect(result.stderr).toBe("");
    const envelope = JSON.parse(result.stdout);
    expect(envelope).toMatchObject({
      version: 2,
      result: {
        status: "success",
        system: {
          equations: [
            { name: "source" },
            { name: "translated", dependencies: ["source"] },
          ],
          dependency_edges: [["source", "translated"]],
          reuse: [
            { producer: "source", consumer: "translated", references: 2 },
          ],
          unknown_costs: ["C_translate"],
          relationships_used: [
            {
              name: "population",
              relationship: systemRequest.assumptions[0].relationship,
            },
          ],
        },
        scenarios: [
          {
            name: "fixed_boxes",
            qualifications: expect.any(Array),
          },
        ],
      },
    });
    expect(Buffer.byteLength(result.stdout)).toBeLessThanOrEqual(262_400);
  });
});
