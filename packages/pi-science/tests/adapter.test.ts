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

const goal = {
  kind: "preserve_all_outputs_v1",
  semantics: "exact_symbolic_v1",
  objective: { kind: "unit_work_v1" },
} as const;
const optimizeRequest = (
  request: Record<string, unknown>,
  projection_limit = 16,
) => ({
  syntax: "sympy",
  operation: "optimize",
  ...request,
  goal,
  search: { kind: "bounded_goal_v1" },
  proof: { kind: "verifier_backed_v1" },
  projection_limit,
});

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
  it("round trips a lexical Let binding under protocol v17", () => {
    const result = invoke(
      JSON.stringify({
        version: 17,
        request: {
          syntax: "sympy",
          expression: "Let(t, x*x, t + t)",
        },
      }),
    );

    expect(result.status).toBe(0);
    expect(JSON.parse(result.stdout)).toMatchObject({
      version: 17,
      result: {
        status: "success",
        interpretation: {
          normalized_sympy: "Let(t, x*x, t + t)",
        },
        abstract_work: 2,
      },
    });

    const malformed = invoke(
      JSON.stringify({
        version: 17,
        request: {
          syntax: "sympy",
          expression: "Let(t, t + 1, t)",
        },
      }),
    );
    expect(malformed.status).toBe(0);
    expect(JSON.parse(malformed.stdout)).toMatchObject({
      version: 17,
      result: {
        status: "failure",
        error: {
          code: "unsupported_construct",
          message: "Let value cannot reference its own name",
          source: { path: "expression" },
        },
      },
    });
  });

  it("replays a projected optimization candidate unchanged", () => {
    const optimized = invoke(
      JSON.stringify({
        version: 17,
        request: optimizeRequest({ expression: "x*x + x*x" }),
      }),
    );
    expect(optimized.status).toBe(0);
    const candidate = JSON.parse(optimized.stdout).result.plans[0].candidate;
    expect(candidate).toMatchObject({
      expression: expect.any(String),
      outputs: ["expression"],
    });
    expect(candidate).not.toHaveProperty("equations");

    const replayed = invoke(
      JSON.stringify({
        version: 17,
        request: { syntax: "sympy", ...candidate },
      }),
    );

    expect(replayed.status).toBe(0);
    expect(JSON.parse(replayed.stdout).result.status).toBe("success");

    const optimizedSystem = invoke(
      JSON.stringify({
        version: 17,
        request: optimizeRequest({
          equations: [
            { name: "a", expression: "Eq(a, x*x + 1)" },
            { name: "b", expression: "Eq(b, x*x - 1)" },
            { name: "untouched", expression: "Eq(untouched, (z + 1))" },
          ],
          variables: { x: { domain: "real" }, z: { domain: "real" } },
        }),
      }),
    );
    expect(optimizedSystem.status).toBe(0);
    const systemPlan = JSON.parse(optimizedSystem.stdout).result.plans.find(
      (plan: { suggestion: { kind: string } }) =>
        plan.suggestion.kind === "cross_equation_sharing",
    );
    expect(systemPlan.candidate.outputs).toEqual(["a", "b", "untouched"]);
    expect(systemPlan.candidate).not.toHaveProperty("expression");
    // Complete states retain every untouched caller equation verbatim, even
    // before a retained parent exists for the first replay step.
    expect(
      systemPlan.candidate.equations.find(
        (equation: { name: string }) => equation.name === "untouched",
      ).expression,
    ).toBe("Eq(untouched, (z + 1))");

    const replayedSystem = invoke(
      JSON.stringify({
        version: 17,
        request: { syntax: "sympy", ...systemPlan.candidate },
      }),
    );
    expect(replayedSystem.status).toBe(0);
    expect(JSON.parse(replayedSystem.stdout).result.status).toBe("success");
  });

  it("keeps ordinary analyses free of optimization controls and results", () => {
    const ordinary = invoke(
      JSON.stringify({
        version: 17,
        request: { syntax: "sympy", expression: "x*y + x*z" },
      }),
    );
    expect(ordinary.status).toBe(0);
    expect(JSON.parse(ordinary.stdout).result).not.toHaveProperty(
      "optimization",
    );

    const rejected = invoke(
      JSON.stringify({
        version: 17,
        request: {
          syntax: "sympy",
          expression: "x",
          optimization: { max_suggestions: 0 },
        },
      }),
    );
    expect(rejected.status).toBe(2);
  });

  it("returns explicit v17 goal-driven plans with claims, scope, and blockers", () => {
    const result = invoke(
      JSON.stringify({
        version: 17,
        request: optimizeRequest({ expression: "x*y + x*z" }),
      }),
    );
    expect(result.status).toBe(0);
    const optimization = JSON.parse(result.stdout).result;
    expect(optimization).toMatchObject({
      status: "success",
      projection_limit: 16,
      classification: "plans_returned",
      selection: { kind: "deterministic_ranked_prefix", projection_limit: 16 },
      search_scope: {
        policy: "bounded_goal_v1",
        monotonic_depth: 2,
        engine: "goal_optimizer_v1",
        completion: "complete",
        qualifications: [],
        limits: { depth_one_inspected_nodes: expect.any(Number) },
      },
      projection_status: "complete",
      projection_qualifications: [],
      blockers: [],
      plans: [
        {
          claim: {
            kind: "strict_improvement",
            proof_policy: "verifier_backed_v1",
            semantics: "exact_symbolic_v1",
            work_semantics: "aggregate_abstract_work_v1",
            search_policy: "bounded_goal_v1",
            monotonic_depth: 2,
            engine: "goal_optimizer_v1",
          },
          suggestion: {
            kind: "factoring",
            objective_before: "3",
            objective_after: "2",
            objective_savings: "1",
          },
        },
      ],
    });
  });

  it("uses all fixed optimization families, including algorithmic finite sums", () => {
    const cases = [
      ["repeated_subexpression", { expression: "(x + 1) * (x + 1)" }],
      ["factoring", { expression: "x*y + x*z" }],
      ["horner", { expression: "2*x**3 + 3*x**2 + 4*x + 5" }],
      [
        "cross_equation_sharing",
        {
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
        },
      ],
      [
        "repeated_call",
        {
          expression: "f(x) + f(x)",
          variables: { x: { domain: "real" } },
          functions: [{ name: "f", parameters: ["z"], body: "z*z" }],
        },
      ],
      [
        "reciprocal_reuse",
        { expression: "1/x + 1/x", variables: { x: { domain: "real" } } },
      ],
      [
        "iterator_invariant_hoisting",
        {
          expression: "Sum(x*x + i, (i, 0, 3))",
          variables: { x: { domain: "real" } },
        },
      ],
      [
        "finite_polynomial_sum_v1",
        { expression: "3 + Sum(Sum(i*j + j**2, (j, 0, i)), (i, 0, 100))" },
      ],
    ] as const;
    for (const [kind, request] of cases) {
      const result = invoke(
        JSON.stringify({ version: 17, request: optimizeRequest(request) }),
      );
      expect(result.status).toBe(0);
      const plan = JSON.parse(result.stdout).result.plans.find(
        (item: { suggestion: { kind: string } }) =>
          item.suggestion.kind === kind,
      );
      expect(plan).toMatchObject({
        claim: {
          kind: "strict_improvement",
          families: expect.arrayContaining(["finite_polynomial_sum_v1"]),
        },
        suggestion: {
          kind,
          tier:
            kind === "finite_polynomial_sum_v1"
              ? "exact_algorithmic_v1"
              : "exact_algebraic_v1",
        },
      });
    }
  });

  it("reports concrete blockers without turning them into optimization failures", () => {
    const result = invoke(
      JSON.stringify({
        version: 17,
        request: optimizeRequest({ expression: "f(x) + f(x)" }),
      }),
    );
    expect(result.status).toBe(0);
    expect(JSON.parse(result.stdout).result).toMatchObject({
      status: "success",
      classification: "no_verified_improvement",
      plans: [],
      blockers: [
        {
          family: "repeated_call",
          reason: "missing_primitive_cost",
          required_information: "declare_primitive_cost",
          target: "expression",
        },
      ],
    });
  });

  it("keeps incomplete search scope distinct from projection status", () => {
    const result = invoke(
      JSON.stringify({
        version: 17,
        request: optimizeRequest({
          equations: Array.from({ length: 128 }, (_, index) => ({
            name: `value_${index}`,
            expression: `Eq(value_${index}, (x + 0) + (y + 0) + (z + 0))`,
          })),
          variables: {
            x: { domain: "real" },
            y: { domain: "real" },
            z: { domain: "real" },
          },
        }),
      }),
    );
    expect(result.status).toBe(0);
    expect(JSON.parse(result.stdout).result).toMatchObject({
      status: "success",
      search_scope: {
        completion: "incomplete",
        qualifications: expect.any(Array),
      },
      projection_status: "complete",
      plans: [],
    });
  }, 30_000);

  it("retains zero-post-work improvements in explicit results", () => {
    const result = invoke(
      JSON.stringify({
        version: 17,
        request: optimizeRequest({ expression: "x + 0" }),
      }),
    );
    expect(result.status).toBe(0);
    expect(JSON.parse(result.stdout).result.plans[0].suggestion).toMatchObject({
      objective_before: "1",
      objective_after: "0",
      objective_savings: "1",
    });
  });

  it.each([
    ["malformed request", "not json"],
    [
      "incompatible protocol",
      JSON.stringify({
        version: 16,
        request: { syntax: "sympy", expression: "x" },
      }),
    ],
    [
      "extra request key",
      JSON.stringify({
        version: 17,
        request: { syntax: "sympy", expression: "x", extra: true },
      }),
    ],
    [
      "invalid request type",
      JSON.stringify({
        version: 17,
        request: { syntax: "sympy", expression: 1 },
      }),
    ],
    [
      "reserved query name",
      JSON.stringify({
        version: 17,
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
        version: 17,
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
        version: 17,
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
        version: 17,
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
      error: { kind: "request" },
    });
  });

  it("bounds serialized output before writing it", () => {
    const code = `
import importlib.util, sys
spec = importlib.util.spec_from_file_location("formula_adapter", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
print(module._encoded({"result": "x" * 524545}) is None)
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

  it("preserves mandatory nulls in populated protocol-v13 query answers", () => {
    const result = invoke(
      JSON.stringify({
        version: 17,
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

  it("round trips partial nested polynomial closed forms under protocol v17", () => {
    const success = invoke(
      JSON.stringify({
        version: 17,
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
      version: 17,
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
        version: 17,
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
        version: 17,
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
        version: 17,
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
      JSON.stringify({ version: 17, request: comparisonRequest }),
    );
    expect(result.status).toBe(0);
    expect(result.stderr).toBe("");
    expect(JSON.parse(result.stdout)).toMatchObject({
      version: 17,
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
      JSON.stringify({ version: 17, request: systemRequest }),
    );
    expect(result.status).toBe(0);
    expect(result.stderr).toBe("");
    const envelope = JSON.parse(result.stdout);
    expect(envelope).toMatchObject({
      version: 17,
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

describe("dominance protocol v17", () => {
  it("round trips canonical bounded integer dominance", () => {
    const result = invoke(
      JSON.stringify({
        version: 17,
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

describe("optimization request contract", () => {
  it("strictly rejects omitted declarative controls and legacy knobs", () => {
    for (const request of [
      { syntax: "sympy", operation: "optimize", expression: "x" },
      { ...optimizeRequest({ expression: "x" }), max_plans: 1 },
      {
        ...optimizeRequest({ expression: "x" }),
        enabled_algorithmic_families: ["finite_polynomial_sum_v1"],
      },
    ]) {
      const result = invoke(JSON.stringify({ version: 17, request }));
      expect(result.status).toBe(2);
    }
  });
});
