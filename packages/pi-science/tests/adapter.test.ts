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
      name: "displacement",
      expression: "Eq(D[i, d], x[i, d] - center[box[i], d])",
      domains: {
        i: { lower: "0", upper: "N - 1" },
        d: { lower: "0", upper: "dim - 1" },
      },
    },
    {
      name: "multipoles",
      expression:
        "Eq(M[b, k], Sum(K(p) * basis(D[i, 0], k), (i, 0, n[b] - 1)))",
      domains: {
        b: { lower: "0", upper: "B - 1" },
        k: { lower: "0", upper: "p - 1" },
      },
    },
    {
      name: "translation",
      expression:
        "Eq(L[b, k], Sum(translate(M[neighbor[b, c], k]) + M[neighbor[b, c], k], (c, 0, C - 1)))",
      domains: {
        b: { lower: "0", upper: "B - 1" },
        k: { lower: "0", upper: "p - 1" },
      },
    },
  ],
  variables: {
    N: { domain: "positive_integer" },
    dim: { domain: "positive_integer" },
    B: { domain: "positive_integer" },
    p: { domain: "positive_integer" },
    C: { domain: "positive_integer" },
    x: { domain: "real" },
    center: { domain: "real" },
    box: { domain: "nonnegative_integer" },
    n: { domain: "nonnegative_integer" },
    neighbor: { domain: "nonnegative_integer" },
  },
  functions: [{ name: "K", parameters: ["z"], body: "z * z" }],
  primitive_costs: [
    { name: "basis", parameters: ["value", "k"], work: "k + 1" },
  ],
  assumptions: [
    {
      name: "population",
      relationship: "Sum(n[b], (b, 0, B - 1)) == N",
    },
  ],
  definitions: [],
  scenarios: [{ name: "fixed_order", fixed: { p: 3 }, asymptotic: ["N"] }],
};

describe("formula adapter protocol boundary", () => {
  it.each([
    ["malformed request", "not json"],
    ["incompatible protocol", JSON.stringify({ version: 1, request: {} })],
    [
      "extra request key",
      JSON.stringify({
        version: 6,
        request: { syntax: "sympy", expression: "x", extra: true },
      }),
    ],
    [
      "invalid request type",
      JSON.stringify({
        version: 6,
        request: { syntax: "sympy", expression: 1 },
      }),
    ],
    [
      "reserved query name",
      JSON.stringify({
        version: 6,
        request: {
          syntax: "sympy",
          expression: "x",
          queries: [{ name: "oo", kind: "equivalence", comparison: "x" }],
        },
      }),
    ],
    [
      "reserved property variable",
      JSON.stringify({
        version: 6,
        request: {
          syntax: "sympy",
          expression: "x",
          queries: [
            {
              name: "q",
              kind: "properties",
              checks: [{ kind: "valid_domain", variable: "oo" }],
            },
          ],
        },
      }),
    ],
    [
      "reserved limit variable",
      JSON.stringify({
        version: 6,
        request: {
          syntax: "sympy",
          expression: "x",
          queries: [
            {
              name: "q",
              kind: "limit",
              variable: "oo",
              point: "0",
              direction: "both",
            },
          ],
        },
      }),
    ],
    [
      "reserved asymptotic variable",
      JSON.stringify({
        version: 6,
        request: {
          syntax: "sympy",
          expression: "x",
          queries: [
            {
              name: "q",
              kind: "asymptotic",
              variable: "oo",
              point: "oo",
              order: 1,
            },
          ],
        },
      }),
    ],
    [
      "duplicate envelope key",
      '{"version":3,"version":3,"request":{"syntax":"sympy","expression":"x"}}',
    ],
    ["oversized envelope", "x".repeat(2_097_153)],
  ])("returns a bounded deterministic error for %s", (_name, input) => {
    const result = invoke(input);
    expect(result.status).toBe(2);
    expect(result.stderr).toBe("");
    expect(Buffer.byteLength(result.stdout)).toBeLessThan(10_000);
    expect(JSON.parse(result.stdout)).toMatchObject({
      version: 6,
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

  it("preserves mandatory nulls in populated protocol-v6 query answers", () => {
    const result = invoke(
      JSON.stringify({
        version: 6,
        request: {
          syntax: "sympy",
          expression: "x",
          queries: [
            { name: "same", kind: "equivalence", comparison: "x" },
            { name: "later", kind: "closed_form" },
          ],
        },
      }),
    );
    expect(result.status).toBe(0);
    const envelope = JSON.parse(result.stdout);
    expect(envelope.result.queries[0].answers[0]).toMatchObject({
      check: null,
      evidence: { kind: "identity" },
    });
    expect(envelope.result.queries[1].answers[0]).toMatchObject({
      check: null,
      evidence: null,
      derived_candidates: [],
    });
  });

  it("canonicalizes exact real scenario values and interval endpoints", () => {
    const result = invoke(
      JSON.stringify({
        version: 6,
        request: {
          syntax: "sympy",
          expression: "primitive(x)",
          variables: { x: { domain: "nonnegative_real" } },
          primitive_costs: [
            { name: "primitive", parameters: ["z"], work: "z + 1" },
          ],
          scenarios: [
            {
              name: "exact",
              fixed: { x: "1.20" },
              bounds: {
                x: { lower: "-0", upper: "2", lower_inclusive: false },
              },
            },
          ],
        },
      }),
    );
    expect(result.status).toBe(2); // One variable cannot have fixed and bound treatments.
    const bounded = invoke(
      JSON.stringify({
        version: 6,
        request: {
          syntax: "sympy",
          expression: "primitive(x)",
          variables: { x: { domain: "nonnegative_real" } },
          primitive_costs: [
            { name: "primitive", parameters: ["z"], work: "z + 1" },
          ],
          scenarios: [
            {
              name: "exact",
              bounds: {
                x: { lower: "-0", upper: "1.20", lower_inclusive: false },
              },
            },
          ],
        },
      }),
    );
    expect(bounded.status).toBe(0);
    expect(
      JSON.parse(bounded.stdout).result.scenarios[0].interval,
    ).toMatchObject({
      lower: "0",
      upper: "6/5",
      lower_inclusive: false,
      infimum_attained: false,
    });
  });

  it("round trips a complete equation-system request through the real adapter", () => {
    const result = invoke(
      JSON.stringify({ version: 6, request: systemRequest }),
    );
    expect(result.status).toBe(0);
    expect(result.stderr).toBe("");
    const envelope = JSON.parse(result.stdout);
    expect(envelope).toMatchObject({
      version: 6,
      result: {
        status: "success",
        system: {
          equations: [
            { name: "displacement" },
            { name: "multipoles", dependencies: ["displacement"] },
            { name: "translation", dependencies: ["multipoles"] },
          ],
          dependency_edges: [
            ["displacement", "multipoles"],
            ["multipoles", "translation"],
          ],
          reuse: [
            { producer: "displacement", consumer: "multipoles", references: 1 },
            { producer: "multipoles", consumer: "translation", references: 2 },
          ],
          total_work:
            "B*p*(2*C - 1) + N*dim + N*p*(p + 1)/2 + p*Sum(2*n[b], (b, 0, B - 1)) + p*Sum(Max(0, n[b] - 1), (b, 0, B - 1)) + Sum(C_translate(M[neighbor[b, c], k]), (c, 0, C - 1), (k, 0, p - 1), (b, 0, B - 1))",
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
            name: "fixed_order",
            qualifications: expect.any(Array),
          },
        ],
      },
    });
    expect(Buffer.byteLength(result.stdout)).toBeLessThanOrEqual(262_400);
  });
});
