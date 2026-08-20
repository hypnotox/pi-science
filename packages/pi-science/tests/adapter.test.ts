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

const comparisonRequest = {
  syntax: "sympy",
  operation: "compare_candidates",
  variables: {
    N: { domain: "nonnegative_integer" },
    x: { domain: "real" },
    d: { domain: "real" },
  },
  candidates: [
    {
      name: "first",
      equations: [
        { name: "rate", expression: "Eq(r, 1 / d)" },
        {
          name: "out",
          expression: "Eq(y[i], x * r)",
          domains: { i: { lower: "0", upper: "N" } },
        },
      ],
    },
    {
      name: "second",
      equations: [
        {
          name: "out",
          expression: "Eq(z[j], x / d)",
          domains: { j: { lower: "0", upper: "N" } },
        },
      ],
    },
  ],
  outputs: [
    {
      name: "value",
      targets: [
        { candidate: "first", target: { kind: "equation", name: "out" } },
        { candidate: "second", target: { kind: "equation", name: "out" } },
      ],
    },
  ],
};

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
  it("round trips local, sharing, Horner, and incomplete optimization reports", () => {
    const requests = [
      { syntax: "sympy", expression: "x" },
      {
        syntax: "sympy",
        expression: "x",
        optimization: { max_suggestions: 0 },
      },
      { syntax: "sympy", expression: "x*y + x*z" },
      {
        syntax: "sympy",
        equations: [
          { name: "value", expression: "Eq(value, (x + 1) * (x + 1))" },
        ],
        variables: { x: { domain: "real" } },
      },
      {
        syntax: "sympy",
        expression: "2*x**3 + 3*x**2 + 4*x + 5",
      },
      {
        syntax: "sympy",
        equations: [
          {
            name: "left",
            expression: "Eq(left[i], x[i]*x[i] + 1)",
            domains: { i: { lower: "0", upper: "3" } },
          },
          {
            name: "right",
            expression: "Eq(right[j], x[j]*x[j] - 1)",
            domains: { j: { lower: "0", upper: "3" } },
          },
        ],
        variables: { x: { domain: "real" } },
        optimization: { max_suggestions: 16 },
      },
      {
        syntax: "sympy",
        equations: Array.from({ length: 128 }, (_, index) => ({
          name: `value_${index}`,
          expression: `Eq(value_${index}, (x + 0) + (y + 0) + (z + 0))`,
        })),
        variables: {
          x: { domain: "real" },
          y: { domain: "real" },
          z: { domain: "real" },
        },
      },
    ];
    const reports = requests.map((request) => {
      const result = invoke(JSON.stringify({ version: 12, request }));
      expect(result.status).toBe(0);
      return JSON.parse(result.stdout).result.optimization;
    });
    expect(reports[0]).toMatchObject({
      requested_limit: 3,
      status: "complete",
      suggestions: [],
    });
    expect(reports[1]).toEqual({
      requested_limit: 0,
      status: "disabled",
      suggestions: [],
      qualifications: [],
    });
    expect(reports[2].suggestions[0]).toMatchObject({
      kind: "factoring",
      transformations: [
        {
          target: { kind: "expression", name: null },
          occurrences: [{ path: [], binders: [], output_indices: [] }],
          original: {
            normalized_sympy: "x*y + x*z",
            normalized_latex: "x y + x z",
          },
          proposed: {
            normalized_sympy: "x*(y + z)",
            normalized_latex: "x \\left(y + z\\right)",
          },
        },
      ],
      intermediate: null,
      work_before: "3",
      work_after: "2",
      savings: "1",
    });
    expect(reports[3].suggestions[0]).toMatchObject({
      kind: "repeated_subexpression",
      transformations: [{ target: { kind: "equation", name: "value" } }],
    });
    expect(reports[4].suggestions[0]).toMatchObject({
      kind: "horner",
      transformations: [{ target: { kind: "expression", name: null } }],
      intermediate: null,
    });
    expect(reports[5].suggestions[0].kind).toBe("cross_equation_sharing");
    expect(
      reports[5].suggestions[0].transformations.map(
        (item: {
          target: { name: string };
          occurrences: Array<{ output_indices: string[] }>;
        }) => [item.target.name, item.occurrences[0].output_indices],
      ),
    ).toEqual([
      ["left", ["i"]],
      ["right", ["j"]],
    ]);
    expect(reports[5].suggestions[0].intermediate.scope_output_indices).toEqual(
      ["i"],
    );
    expect(reports[6]).toMatchObject({
      requested_limit: 3,
      status: "incomplete",
    });
    expect(reports[6].qualifications[0]).toContain("generated candidates");
    expect(reports[6].qualifications[0]).toContain("measured");
    expect(reports[6].qualifications[0]).toContain("configured");
    expect(reports[6].suggestions.length).toBeGreaterThan(0);
  });

  it.each([
    ["malformed request", "not json"],
    [
      "incompatible protocol",
      JSON.stringify({
        version: 11,
        request: {
          syntax: "sympy",
          expression: "x*y + x*z",
          optimization: { max_suggestions: 3 },
        },
      }),
    ],
    [
      "extra request key",
      JSON.stringify({
        version: 12,
        request: { syntax: "sympy", expression: "x", extra: true },
      }),
    ],
    [
      "invalid request type",
      JSON.stringify({
        version: 12,
        request: { syntax: "sympy", expression: 1 },
      }),
    ],
    [
      "reserved query name",
      JSON.stringify({
        version: 12,
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
        version: 12,
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
        version: 12,
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
        version: 12,
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
      version: 12,
      error: { kind: "request" },
    });
  });

  it("bounds serialized output before writing it", () => {
    const code = `
import importlib.util, sys
spec = importlib.util.spec_from_file_location("formula_adapter", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
print(module._encoded({"result": "x" * 327937}) is None)
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

  it("preserves mandatory nulls in populated protocol-v12 query answers", () => {
    const result = invoke(
      JSON.stringify({
        version: 12,
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

  it("round trips partial nested polynomial closed forms under protocol v12", () => {
    const success = invoke(
      JSON.stringify({
        version: 12,
        request: {
          syntax: "sympy",
          expression: "Sum(Sum(1, (l, -k, k)), (k, 0, p))",
          variables: { p: { domain: "nonnegative_integer" } },
          queries: [
            { name: "closed", kind: "closed_form" },
            {
              name: "same",
              kind: "equivalence",
              target: { kind: "derived", query: "closed" },
              comparison: "(p + 1)**2",
            },
          ],
        },
      }),
    );
    expect(success.status).toBe(0);
    const envelope = JSON.parse(success.stdout);
    expect(envelope).toMatchObject({
      version: 12,
      result: {
        status: "success",
        system: { equations: [{ name: "expression" }] },
        queries: [
          {
            name: "closed",
            kind: "closed_form",
            answers: [
              {
                conclusion: "proved",
                evidence: {
                  kind: "closed_form",
                  verification: "finite_antidifference",
                },
                derived_candidates: [
                  {
                    interpretation: { normalized_sympy: "(p + 1)**2" },
                  },
                ],
              },
            ],
          },
          {
            name: "same",
            kind: "equivalence",
            target: { kind: "derived", query: "closed" },
            answers: [{ conclusion: "proved" }],
          },
        ],
      },
    });

    const unresolved = invoke(
      JSON.stringify({
        version: 12,
        request: {
          syntax: "sympy",
          expression: "Sum(Sum(1, (l, -k, k)), (k, -1, 1))",
          queries: [{ name: "closed", kind: "closed_form" }],
        },
      }),
    );
    expect(unresolved.status).toBe(0);
    expect(
      JSON.parse(unresolved.stdout).result.queries[0].answers[0],
    ).toMatchObject({
      conclusion: "unresolved",
      blockers: ["nested polynomial range ordering is unresolved"],
      evidence: null,
      derived_candidates: [],
    });
  });

  it("canonicalizes exact real scenario values and interval endpoints", () => {
    const result = invoke(
      JSON.stringify({
        version: 12,
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
        version: 12,
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

  it("round trips candidate comparison through the real adapter", () => {
    const result = invoke(
      JSON.stringify({ version: 12, request: comparisonRequest }),
    );
    expect(result.status).toBe(0);
    expect(result.stderr).toBe("");
    expect(JSON.parse(result.stdout)).toMatchObject({
      version: 12,
      result: {
        kind: "candidate_comparison",
        status: "success",
        candidates: [
          { name: "first", aggregate_work: expect.any(String) },
          { name: "second", aggregate_work: expect.any(String) },
        ],
        outputs: [
          {
            name: "value",
            targets: [{ candidate: "first" }, { candidate: "second" }],
            interface_status: "compatible",
            answer: {
              conclusion: "proved_under_assumptions",
              evidence: { kind: "identity" },
            },
          },
        ],
        semantic_status: "proved_equal_under_assumptions",
        work_comparison: {
          candidate_names: ["first", "second"],
          delta: "-1",
          status: "second_lower",
          evidence: { kind: "property" },
        },
      },
    });
  });

  it("round trips a complete equation-system request through the real adapter", () => {
    const result = invoke(
      JSON.stringify({ version: 12, request: systemRequest }),
    );
    expect(result.status).toBe(0);
    expect(result.stderr).toBe("");
    const envelope = JSON.parse(result.stdout);
    expect(envelope).toMatchObject({
      version: 12,
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
    expect(Buffer.byteLength(result.stdout)).toBeLessThanOrEqual(327_936);
  });
});

describe("dominance protocol v12", () => {
  it("round trips canonical bounded integer dominance", () => {
    const result = invoke(
      JSON.stringify({
        version: 12,
        request: {
          syntax: "sympy",
          operation: "analyze_dominance",
          expression: "cost(N)",
          axis: "N",
          variables: { N: { domain: "nonnegative_integer" } },
          primitive_costs: [
            { name: "cost", parameters: ["n"], work: "n**2 - n + 1" },
          ],
        },
      }),
    );
    expect(result.status).toBe(0);
    const dominance = JSON.parse(result.stdout).result;
    expect(dominance).toMatchObject({
      kind: "dominance_analysis",
      dominance_status: "complete",
      axis: "N",
    });
    expect(dominance.terms.map((term: { id: string }) => term.id)).toEqual([
      "power:2",
      "power:1",
      "power:0",
    ]);
    expect(dominance.cells[1]).toMatchObject({
      kind: "integer_point",
      value: "1",
      dominant: ["power:2", "power:1", "power:0"],
    });
    expect(dominance.cells[2]).toMatchObject({
      kind: "integer_range",
      lower: "2",
      upper: "oo",
      dominant: ["power:2"],
    });
    expect(dominance.analysis.status).toBe("success");
  });
});
