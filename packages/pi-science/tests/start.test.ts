import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import type { TSchema } from "typebox";
import { Value } from "typebox/value";
import { describe, expect, it, vi } from "vitest";
import {
  type FormulaParameters,
  formulaSchema,
  resolvePinnedRevision,
  resolvePinnedSource,
  start,
} from "../src/index.js";
import {
  afmmParameters,
  afmmTailParameters,
  afmmTotalWork,
} from "./afmm-fixture.js";

const repositoryRoot = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "../../..",
);

type Command = {
  handler(args: string, context: unknown): Promise<void>;
};
type Tool = {
  description: string;
  promptSnippet?: string;
  promptGuidelines?: string[];
  parameters: TSchema;
  execute(
    id: string,
    params: FormulaParameters,
    signal?: AbortSignal,
  ): Promise<{
    content: Array<{ type: string; text: string }>;
    details: unknown;
  }>;
};
type EventHandler = (event: unknown, context: unknown) => Promise<void>;

const expressionQueryWithTarget: FormulaParameters = {
  expression: "x",
  queries: [
    {
      name: "invalid",
      kind: "closed_form",
      // @ts-expect-error Expression-context queries must not select an equation.
      target: { kind: "equation", name: "stage" },
    },
  ],
};
void expressionQueryWithTarget;
// @ts-expect-error System-context queries must select a named equation.
const systemQueryWithoutTarget: FormulaParameters = {
  equations: [{ name: "stage", expression: "Eq(y, x)" }],
  queries: [{ name: "invalid", kind: "closed_form" }],
};
void systemQueryWithoutTarget;

function host() {
  const commands = new Map<string, Command>();
  const tools: Tool[] = [];
  const events = new Map<string, EventHandler>();
  const api = {
    registerCommand: vi.fn((name: string, command: Command) => {
      commands.set(name, command);
    }),
    registerTool: vi.fn((tool: Tool) => {
      tools.push(tool);
    }),
    on: vi.fn((name: string, handler: EventHandler) => {
      events.set(name, handler);
    }),
  } as unknown as ExtensionAPI;
  return { api, commands, tools, events };
}

function context(hasUI: boolean) {
  return {
    hasUI,
    ui: { notify: vi.fn() },
  };
}

describe("readiness gate", () => {
  it("advertises bounded optimization advice and uses the real command signature", async () => {
    const current = host();
    const response = {
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
      direct_work_applicability: "finite",
      direct_work_blockers: [],
      scenarios: [],
      queries: [],
      optimization: {
        requested_limit: 3,
        status: "complete",
        suggestions: [],
        qualifications: [],
      },
    };
    await start(
      current.api,
      Promise.resolve({
        ready: true,
        command: process.execPath,
        args: [
          "-e",
          `process.stdin.resume();process.stdin.on("end",()=>process.stdout.write(${JSON.stringify(
            JSON.stringify({ version: 12, result: response }),
          )}))`,
        ],
      }),
    );
    expect(current.commands.has("pi-science-doctor")).toBe(true);
    expect(current.tools).toHaveLength(1);
    expect(current.tools[0]).toMatchObject({
      description: expect.stringMatching(
        /restricted SymPy.*bounded exact-symbolic optimization advice.*candidate.*dominance/,
      ),
      promptSnippet: expect.stringMatching(
        /qualified symbolic work.*bounded exact-symbolic optimization advice.*candidate.*dominance/,
      ),
      promptGuidelines: [
        expect.stringMatching(
          /Before first using analyze_formula.*pi-science-formula-analysis skill/,
        ),
        expect.stringMatching(/analyze_formula rejects.*Python-owned message/),
      ],
    });
    const parameters = current.tools[0]!.parameters;
    expect(Value.Check(parameters, { expression: "x" })).toBe(true);
    const comparison = {
      operation: "compare_candidates",
      candidates: [
        { name: "first", expression: "x" },
        { name: "second", expression: "x + 0" },
      ],
      outputs: [
        {
          name: "value",
          targets: [
            { candidate: "first", target: { kind: "expression" } },
            { candidate: "second", target: { kind: "expression" } },
          ],
        },
      ],
    };
    expect(Value.Check(parameters, comparison)).toBe(true);
    expect(
      Value.Check(parameters, {
        ...comparison,
        candidates: [{ name: "first" }, comparison.candidates[1]],
      }),
    ).toBe(false);
    expect(
      Value.Check(parameters, {
        ...comparison,
        candidates: [
          { name: "first", expression: "x", equations: [] },
          comparison.candidates[1],
        ],
      }),
    ).toBe(false);
    expect(
      Value.Check(parameters, {
        equations: [
          {
            name: "stage",
            expression: "Eq(y[i], x[i] + 1)",
            domains: { i: { lower: "0", upper: "N - 1" } },
          },
        ],
        variables: { N: { domain: "positive_integer" } },
        functions: [{ name: "f", parameters: ["x"], body: "x + 1" }],
        primitive_costs: [{ name: "g", parameters: ["x"], work: "x" }],
        assumptions: [{ name: "known", relationship: "N > 0" }],
        definitions: [{ variable: "p", expression: "N + 1" }],
        scenarios: [{ name: "scale", asymptotic: ["N"] }],
      }),
    ).toBe(true);
    expect(
      Value.Check(parameters, {
        expression: "x",
        queries: [
          { name: "same", kind: "equivalence", comparison: "x" },
          { name: "domain", kind: "properties", checks: [{ kind: "sign" }] },
          {
            name: "at_zero",
            kind: "limit",
            variable: "x",
            point: "0",
            direction: "both",
          },
          {
            name: "at_infinity",
            kind: "asymptotic",
            variable: "x",
            point: "oo",
            order: 2,
          },
        ],
      }),
    ).toBe(true);
    expect(
      Value.Check(parameters, {
        expression: "x",
        variables: { x: { domain: "nonnegative_real" } },
        scenarios: [
          {
            name: "exact",
            fixed: { x: "1/2" },
            choices: { y: [0, "1.20"] },
            bounds: {
              z: {
                lower: "-3/4",
                upper: "1.20",
                lower_inclusive: false,
                upper_inclusive: true,
              },
            },
          },
        ],
      }),
    ).toBe(true);
    for (const invalid of [
      {},
      { expression: "x", equations: [{ name: "a", expression: "Eq(a, x)" }] },
      { equations: [] },
      { expression: "x", syntax: "latex" },
      { expression: "x", extra: true },
      { equations: [{ name: "a", expression: "Eq(a, x)", extra: true }] },
      {
        expression: "x",
        queries: [{ name: "missing_kind", comparison: "x" }],
      },
      {
        expression: "x",
        queries: [
          { name: "missing_check_kind", kind: "properties", checks: [{}] },
        ],
      },
      {
        expression: "x",
        queries: [
          {
            name: "bad",
            kind: "equivalence",
            comparison: "x",
            target: { kind: "expression" },
          },
        ],
      },
      {
        equations: [{ name: "a", expression: "Eq(a, x)" }],
        queries: [{ name: "missing_target", kind: "closed_form" }],
      },
    ])
      expect(Value.Check(parameters, invalid)).toBe(false);
    for (const pythonValidated of [
      {
        expression: "x",
        scenarios: [
          { name: "unsafe", fixed: { N: Number.MAX_SAFE_INTEGER + 1 } },
        ],
      },
      {
        expression: "x",
        queries: [{ name: "bad", kind: "limit", variable: "x", point: "0" }],
      },
      {
        expression: "x",
        queries: [
          {
            name: "bad",
            kind: "asymptotic",
            variable: "x",
            point: "oo",
            direction: "both",
            order: 1,
          },
        ],
      },
      {
        expression: "x",
        queries: [{ name: "oo", kind: "closed_form" }],
      },
      {
        equations: [{ name: "a", expression: "Eq(a, x)" }],
        queries: [
          {
            name: "bad_target",
            kind: "closed_form",
            target: { kind: "equation", name: "oo" },
          },
        ],
      },
      {
        expression: "x",
        queries: [
          {
            name: "bad_variable",
            kind: "limit",
            variable: "oo",
            point: "0",
            direction: "both",
          },
        ],
      },
      {
        expression: "x",
        queries: [
          {
            name: "bad",
            kind: "properties",
            checks: [{ kind: "sign" }, { kind: "sign" }],
          },
        ],
      },
    ])
      expect(Value.Check(parameters, pythonValidated)).toBe(true);
    const result = await current.tools[0]?.execute("id", { expression: "x" });
    expect(result).toEqual({
      content: [
        {
          type: "text",
          text: [
            "Interpretation",
            "- SymPy: x",
            "- LaTeX: x",
            "Query conclusions",
            "- none",
            "Work",
            "- General direct work: 0",
            "- Specialized evaluation work: none",
            "Optimization advice",
            "- no proved opportunity found within completed search",
            "Blockers",
            "- none",
          ].join("\n"),
        },
      ],
      details: response,
    });
  });

  it("presents first-ranked optimization advice compactly with canonical details", async () => {
    const current = host();
    const adapter = fileURLToPath(
      new URL("../bridge/formula_adapter.py", import.meta.url),
    );
    await start(
      current.api,
      Promise.resolve({
        ready: true,
        command: "uv",
        args: ["run", "--locked", "python", adapter],
      }),
    );
    const result = await current.tools[0]!.execute("id", {
      expression: "x*y + x*z",
    });
    const text = result.content[0]!.text;
    expect(text).toContain("Optimization advice");
    expect(text).toContain("first-ranked proved suggestion");
    expect(text).toContain("factoring: expression: x*y + x*z → x*(y + z)");
    expect(text).toContain("work 3 → 2; saves 1");
    expect(text).toContain("exact_symbolic_only");
    expect(result.details).toMatchObject({
      optimization: {
        requested_limit: 3,
        status: "complete",
        suggestions: [
          {
            kind: "factoring",
            work_before: "3",
            work_after: "2",
            savings: "1",
          },
        ],
      },
    });
  });

  it("presents Python-ranked incomparable advice without claiming superiority", async () => {
    const current = host();
    const suggestion = (
      kind: "factoring" | "horner",
      proposed: string,
      workAfter: string,
      savings: string,
    ) => ({
      kind,
      transformations: [
        {
          target: { kind: "expression", name: null },
          occurrences: [{ path: [], binders: [], output_indices: [] }],
          original: { normalized_sympy: "x", normalized_latex: "x" },
          proposed: { normalized_sympy: proposed, normalized_latex: proposed },
        },
      ],
      intermediate: null,
      conclusion: "proved",
      evidence: { kind: "identity", statement: "verified" },
      conditions: [],
      assumptions_used: [],
      work_before: "N + M + 4",
      work_after: workAfter,
      savings,
      finite_precision_qualification: "exact_symbolic_only",
    });
    const response = {
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
      direct_work_applicability: "finite",
      direct_work_blockers: [],
      scenarios: [],
      queries: [],
      optimization: {
        requested_limit: 3,
        status: "complete",
        suggestions: [
          suggestion("factoring", "first_candidate", "M + 4", "N"),
          suggestion("horner", "second_candidate", "N + 4", "M"),
        ],
        qualifications: [],
      },
    };
    await start(
      current.api,
      Promise.resolve({
        ready: true,
        command: process.execPath,
        args: [
          "-e",
          `process.stdin.resume();process.stdin.on("end",()=>process.stdout.write(${JSON.stringify(
            JSON.stringify({ version: 12, result: response }),
          )}))`,
        ],
      }),
    );

    const result = await current.tools[0]!.execute("id", {
      expression: "x",
      variables: {
        N: { domain: "positive_integer" },
        M: { domain: "positive_integer" },
      },
    });
    const text = result.content[0]!.text;
    expect(text).toContain(
      "first-ranked proved suggestion: factoring: expression: x → first_candidate",
    );
    expect(text).toContain("1 additional proved suggestion in details");
    expect(text).not.toContain("second_candidate");
    expect(text).not.toMatch(/best|superior/i);
    expect(result.details).toMatchObject({
      optimization: {
        suggestions: [
          { kind: "factoring", savings: "N" },
          { kind: "horner", savings: "M" },
        ],
      },
    });
  });

  it("keeps disabled optimization advice out of compact output", async () => {
    const current = host();
    const adapter = fileURLToPath(
      new URL("../bridge/formula_adapter.py", import.meta.url),
    );
    await start(
      current.api,
      Promise.resolve({
        ready: true,
        command: "uv",
        args: ["run", "--locked", "python", adapter],
      }),
    );
    const result = await current.tools[0]!.execute("id", {
      expression: "x*y + x*z",
      optimization: { max_suggestions: 0 },
    });
    expect(result.content[0]!.text).not.toContain("Optimization advice");
    expect(result.details).toMatchObject({
      optimization: { status: "disabled", suggestions: [] },
    });
  });

  it("keeps complete compact transformations and every retained qualification visible", async () => {
    const current = host();
    const longReplacement = `x + ${"y".repeat(600)}`;
    const suggestion = {
      kind: "factoring",
      transformations: [
        {
          target: { kind: "expression", name: null },
          occurrences: [{ path: [], binders: [], output_indices: [] }],
          original: { normalized_sympy: "x + y", normalized_latex: "x+y" },
          proposed: {
            normalized_sympy: longReplacement,
            normalized_latex: "p",
          },
        },
      ],
      intermediate: null,
      conclusion: "proved_under_assumptions",
      evidence: { kind: "identity", statement: "verified" },
      conditions: [],
      assumptions_used: [{ name: "known", relationship: "x > 0" }],
      work_before: "3",
      work_after: "2",
      savings: "1",
      finite_precision_qualification: "exact_symbolic_only",
    };
    const response = {
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
      direct_work_applicability: "finite",
      direct_work_blockers: [],
      scenarios: [],
      queries: [],
      optimization: {
        requested_limit: 3,
        status: "incomplete",
        suggestions: [
          suggestion,
          {
            ...suggestion,
            kind: "redundant_operation_removal",
            conclusion: "proved",
            assumptions_used: [],
          },
        ],
        qualifications: [
          "optimization inspected nodes budget exhausted (measured 4, configured 3)",
        ],
      },
    };
    await start(
      current.api,
      Promise.resolve({
        ready: true,
        command: process.execPath,
        args: [
          "-e",
          `process.stdin.resume();process.stdin.on("end",()=>process.stdout.write(${JSON.stringify(
            JSON.stringify({ version: 12, result: response }),
          )}))`,
        ],
      }),
    );

    const result = await current.tools[0]!.execute("id", {
      expression: "x",
      assumptions: [{ name: "known", relationship: "x > 0" }],
    });
    const text = result.content[0]!.text;
    expect(text).toContain("first-ranked proved suggestion");
    expect(text).toContain(longReplacement);
    expect(text).not.toContain(`${longReplacement.slice(0, 512)}...`);
    expect(text).toContain("assumptions used: known (x > 0)");
    expect(text).toContain("1 additional proved suggestion in details");
    expect(text).toContain(
      "search incomplete; inspect details for the local bound",
    );
    expect(text).toContain(
      "qualification: optimization inspected nodes budget exhausted (measured 4, configured 3)",
    );
  });

  it("keeps empty incomplete-search qualifications visible", async () => {
    const current = host();
    const response = {
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
      direct_work_applicability: "finite",
      direct_work_blockers: [],
      scenarios: [],
      queries: [],
      optimization: {
        requested_limit: 3,
        status: "incomplete",
        suggestions: [],
        qualifications: [
          "optimization proof nodes budget exhausted (measured 4, configured 3)",
        ],
      },
    };
    await start(
      current.api,
      Promise.resolve({
        ready: true,
        command: process.execPath,
        args: [
          "-e",
          `process.stdin.resume();process.stdin.on("end",()=>process.stdout.write(${JSON.stringify(
            JSON.stringify({ version: 12, result: response }),
          )}))`,
        ],
      }),
    );

    const result = await current.tools[0]!.execute("id", { expression: "x" });
    const text = result.content[0]!.text;
    expect(text).toContain(
      "search incomplete; no proved suggestion was retained",
    );
    expect(text).toContain(
      "qualification: optimization proof nodes budget exhausted (measured 4, configured 3)",
    );
  });

  it("renders one atomic multi-target suggestion without a primary target", async () => {
    const current = host();
    const adapter = fileURLToPath(
      new URL("../bridge/formula_adapter.py", import.meta.url),
    );
    await start(
      current.api,
      Promise.resolve({
        ready: true,
        command: "uv",
        args: ["run", "--locked", "python", adapter],
      }),
    );
    const result = await current.tools[0]!.execute("id", {
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
    });
    const text = result.content[0]!.text;
    expect(text).toContain("first-ranked proved suggestion");
    expect(text).toContain("cross_equation_sharing:");
    expect(text).toContain("equation left:");
    expect(text).toContain("equation right:");
    expect(text).toContain("shared intermediate");
    expect(text).toContain("exact_symbolic_only");
    expect(text).not.toContain("primary target");
  });

  it("surfaces localized dominance blockers in compact output", async () => {
    const current = host();
    const adapter = fileURLToPath(
      new URL("../bridge/formula_adapter.py", import.meta.url),
    );
    await start(
      current.api,
      Promise.resolve({
        ready: true,
        command: "uv",
        args: ["run", "--locked", "python", adapter],
      }),
    );
    const result = await current.tools[0]!.execute("id", {
      operation: "analyze_dominance",
      expression: "cost(N)",
      axis: "N",
      variables: { N: { domain: "real" } },
      primitive_costs: [{ name: "cost", parameters: ["n"], work: "n**3 + 2" }],
    });
    expect(result.content[0]!.text).toContain(
      "- -oo to oo: exact factor sign chart is unsupported",
    );
    expect(result.content[0]!.text).not.toContain("Blockers\n- none");
    expect(result.details).toMatchObject({
      kind: "dominance_analysis",
      dominance_status: "unresolved",
      blockers: [],
    });
  });

  it("round trips candidate comparison through the registered tool", async () => {
    const current = host();
    const adapter = fileURLToPath(
      new URL("../bridge/formula_adapter.py", import.meta.url),
    );
    await start(
      current.api,
      Promise.resolve({
        ready: true,
        command: "uv",
        args: ["run", "--locked", "python", adapter],
      }),
    );
    const result = await current.tools[0]!.execute("id", {
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
            {
              candidate: "first",
              target: { kind: "equation", name: "out" },
            },
            {
              candidate: "second",
              target: { kind: "equation", name: "out" },
            },
          ],
        },
      ],
    });
    expect(result.details).toMatchObject({
      kind: "candidate_comparison",
      semantic_status: "proved_equal_under_assumptions",
      work_comparison: { delta: "-1", status: "second_lower" },
    });
    const text = result.content[0]!.text;
    expect(text).toContain("Overall semantic status");
    expect(text).toContain("Mapped-output blockers");
    expect(text).toContain("Delta (second - first): -1");
    expect(text.indexOf("Overall semantic status")).toBeLessThan(
      text.indexOf("Aggregate work"),
    );
    expect(text.indexOf("Mapped-output blockers")).toBeLessThan(
      text.indexOf("Work decision"),
    );
  });

  it("projects closed-form candidates and variable-qualified property checks", async () => {
    const current = host();
    const response = {
      status: "success" as const,
      interpretation: { normalized_sympy: "f(q)", normalized_latex: "f(q)" },
      operation_counts: {
        additions: 0,
        subtractions: 0,
        multiplications: 0,
        divisions: 0,
        powers: 0,
      },
      abstract_work: 0,
      direct_work_applicability: "finite" as const,
      direct_work_blockers: [],
      scenarios: [],
      queries: [
        {
          name: "tail",
          kind: "closed_form" as const,
          target: { kind: "expression" as const },
          normalized_target: {
            normalized_sympy: "f(q)",
            normalized_latex: "f(q)",
          },
          summary: "tail closed form",
          answers: [
            {
              check: null,
              conclusion: "proved_under_assumptions",
              conditions: [],
              assumptions_used: [],
              relevant_unsupported_assumptions: [],
              blockers: [],
              evidence: {
                kind: "closed_form",
                verification: "infinite_partial_sum",
                statement: "verified",
              },
              derived_candidates: [
                {
                  interpretation: {
                    normalized_sympy: "q**p/(1 - q)",
                    normalized_latex: "\\\\frac{q^p}{1-q}",
                  },
                  operation_counts: {
                    additions: 0,
                    subtractions: 1,
                    multiplications: 1,
                    divisions: 1,
                    powers: 1,
                  },
                },
              ],
              constraint_uses: [],
            },
          ],
        },
        {
          name: "shape",
          kind: "properties" as const,
          target: { kind: "expression" as const },
          normalized_target: {
            normalized_sympy: "f(q)",
            normalized_latex: "f(q)",
          },
          summary: "properties",
          answers: [
            {
              check: { kind: "monotonicity", variable: "q" },
              conclusion: "proved",
              conditions: [],
              assumptions_used: [],
              relevant_unsupported_assumptions: [],
              blockers: [],
              evidence: {
                kind: "property",
                value: "increasing",
                intervals: [],
              },
              derived_candidates: [],
              constraint_uses: [],
            },
            {
              check: { kind: "singularities", variable: "p" },
              conclusion: "proved_under_assumptions",
              conditions: [],
              assumptions_used: [],
              relevant_unsupported_assumptions: [],
              blockers: [],
              evidence: { kind: "property", value: "none", intervals: [] },
              derived_candidates: [],
              constraint_uses: [],
            },
          ],
        },
      ],
      optimization: {
        requested_limit: 3,
        status: "complete",
        suggestions: [],
        qualifications: [],
      },
    };
    await start(
      current.api,
      Promise.resolve({
        ready: true,
        command: process.execPath,
        args: [
          "-e",
          `process.stdin.resume();process.stdin.on("end",()=>process.stdout.write(${JSON.stringify(
            JSON.stringify({ version: 12, result: response }),
          )}))`,
        ],
      }),
    );

    const result = await current.tools[0]!.execute("id", {
      expression: "f(q)",
      queries: [
        { name: "tail", kind: "closed_form" },
        {
          name: "shape",
          kind: "properties",
          checks: [
            { kind: "monotonicity", variable: "q" },
            { kind: "singularities", variable: "p" },
          ],
        },
      ],
    });

    expect(result.content[0]!.text).toContain(
      "- tail (closed_form): proved_under_assumptions; derived: q**p/(1 - q)",
    );
    expect(result.content[0]!.text).toContain(
      "- shape (properties; monotonicity (q)): proved",
    );
    expect(result.content[0]!.text).toContain(
      "- shape (properties; singularities (p)): proved_under_assumptions",
    );
    expect(result.details).toEqual(response);
  });

  it("round trips an AFMM-like system through the registered tool callback", async () => {
    const current = host();
    const adapter = fileURLToPath(
      new URL("../bridge/formula_adapter.py", import.meta.url),
    );
    await start(
      current.api,
      Promise.resolve({
        ready: true,
        command: "uv",
        args: ["run", "--locked", "python", adapter],
      }),
    );
    const params: FormulaParameters = afmmParameters;
    const result = await current.tools[0]!.execute("id", params);
    expect(result.details).toMatchObject({
      status: "success",
      system: {
        equations: [
          {
            name: "displacement",
            interpretation: {
              normalized_sympy: "Eq(D[i, d], -center[box[i], d] + x[i, d])",
            },
          },
          {
            name: "multipoles",
            dependencies: ["displacement"],
            interpretation: {
              normalized_sympy:
                "Eq(M[b, k], Sum(K(p)*basis(D[i, 0], k), (i, 0, n[b] - 1)))",
            },
          },
          {
            name: "translation",
            dependencies: ["multipoles"],
            interpretation: {
              normalized_sympy:
                "Eq(L[b, k], Sum(translate(M[neighbor[b, c], k]) + M[neighbor[b, c], k], (c, 0, C - 1)))",
            },
          },
        ],
        dependency_edges: [
          ["displacement", "multipoles"],
          ["multipoles", "translation"],
        ],
        reuse: [
          { producer: "displacement", consumer: "multipoles", references: 1 },
          { producer: "multipoles", consumer: "translation", references: 2 },
        ],
        total_work: afmmTotalWork,
        relationships_used: [
          {
            name: "population",
            relationship: "Sum(n[b], (b, 0, B - 1)) == N",
          },
        ],
        unknown_costs: ["C_translate"],
      },
      scenarios: [
        {
          name: "fixed_order",
          qualifications: [
            "exact general symbolic work preserved",
            "fixed values substituted exactly",
          ],
        },
      ],
    });
    expect(result.content[0]?.text).toContain(
      "Specialized evaluation work (scenario fixed_order):",
    );
    expect(result.content[0]?.text).not.toContain("substituted_work");
    expect(result.content[0]?.text).not.toBe(JSON.stringify(result.details));
  });

  it("keeps nested finite-work iterators bound through the registered tool", async () => {
    const current = host();
    const adapter = fileURLToPath(
      new URL("../bridge/formula_adapter.py", import.meta.url),
    );
    await start(
      current.api,
      Promise.resolve({
        ready: true,
        command: "uv",
        args: ["run", "--locked", "python", adapter],
      }),
    );
    const result = await current.tools[0]!.execute("id", {
      expression: "Sum(Sum(x[j] + primitive(k), (j, k, n)), (k, 0, p - 1))",
      variables: {
        n: { domain: "nonnegative_integer" },
        p: { domain: "nonnegative_integer" },
        x: { domain: "real" },
      },
      primitive_costs: [
        { name: "primitive", parameters: ["value"], work: "value" },
      ],
      scenarios: [{ name: "fixed_order", fixed: { p: 4 } }],
    });
    expect(result.details).toMatchObject({
      status: "success",
      system: { primitive_invocations: { primitive: expect.any(String) } },
      scenarios: [
        { name: "fixed_order", substituted_work: expect.any(String) },
      ],
    });
    expect(result.details).toMatchObject({
      system: {
        total_work: expect.stringContaining(
          "Sum(k*Max(0, -k + n + 1), (k, 0, p - 1))",
        ),
        primitive_invocations: {
          primitive: "Sum(Max(0, -k + n + 1), (k, 0, p - 1))",
        },
      },
      scenarios: [
        {
          substituted_work: expect.stringContaining(
            "Sum(k*Max(0, -k + n + 1), (k, 0, 3))",
          ),
        },
      ],
    });
  });

  it("round trips an acyclic affine output domain through the registered tool", async () => {
    const current = host();
    const adapter = fileURLToPath(
      new URL("../bridge/formula_adapter.py", import.meta.url),
    );
    await start(
      current.api,
      Promise.resolve({
        ready: true,
        command: "uv",
        args: ["run", "--locked", "python", adapter],
      }),
    );
    const parameters: FormulaParameters = {
      equations: [
        {
          name: "triangular",
          expression: "Eq(A[n, m], x + 1)",
          domains: {
            n: { lower: "0", upper: "p" },
            m: { lower: "-n", upper: "n" },
          },
        },
      ],
      variables: {
        p: { domain: "nonnegative_integer" },
        x: { domain: "real" },
      },
      scenarios: [
        { name: "p12", fixed: { p: 12 } },
        { name: "p20", fixed: { p: 20 } },
      ],
    };
    expect(Value.Check(formulaSchema, parameters)).toBe(true);
    const result = await current.tools[0]!.execute("id", parameters);
    expect(result.details).toMatchObject({
      status: "success",
      system: {
        total_work: "(p + 1)**2",
        unresolved: [],
        equations: [
          {
            interpretation: { normalized_sympy: "Eq(A[n, m], x + 1)" },
            aggregate_work: "(p + 1)**2",
          },
        ],
      },
      scenarios: [
        { name: "p12", substituted_work: "169", unresolved: [] },
        { name: "p20", substituted_work: "441", unresolved: [] },
      ],
    });
  });

  it("round trips the harmonic-style affine acceptance system through Python policy", async () => {
    const current = host();
    const adapter = fileURLToPath(
      new URL("../bridge/formula_adapter.py", import.meta.url),
    );
    await start(
      current.api,
      Promise.resolve({
        ready: true,
        command: "uv",
        args: ["run", "--locked", "python", adapter],
      }),
    );
    const result = await current.tools[0]!.execute("id", {
      equations: [
        { name: "ratio_t", expression: "Eq(r_t, h_t / sigma)" },
        { name: "ratio_s", expression: "Eq(r_s, h_s / sigma)" },
        {
          name: "factor_t",
          expression: "Eq(a[n], r_t**n)",
          domains: { n: { lower: "0", upper: "p" } },
        },
        {
          name: "factor_s",
          expression: "Eq(b[k], r_s**k)",
          domains: { k: { lower: "0", upper: "p" } },
        },
        {
          name: "scale",
          expression: "Eq(S[n, k], a[n] * b[k])",
          domains: {
            n: { lower: "0", upper: "p" },
            k: { lower: "0", upper: "p" },
          },
        },
        {
          name: "translation",
          expression:
            "Eq(L[n, m], a[n] * Sum(b[k] * Sum(conjugate(M[k, l]) * harmonic(n + k, m + l), (l, -k, k)), (k, 0, p)))",
          domains: {
            n: { lower: "0", upper: "p" },
            m: { lower: "-n", upper: "n" },
          },
        },
      ],
      variables: {
        p: { domain: "positive_integer" },
        h_t: { domain: "positive_real" },
        h_s: { domain: "positive_real" },
        sigma: { domain: "positive_real" },
        M: { domain: "real" },
      },
      primitive_costs: [
        { name: "conjugate", parameters: ["value"], work: "1" },
        { name: "harmonic", parameters: ["degree", "order"], work: "1" },
      ],
      scenarios: [
        { name: "p12", fixed: { p: 12 } },
        { name: "p20", fixed: { p: 20 } },
      ],
    });
    expect(result.details).toMatchObject({
      status: "success",
      system: {
        dependency_edges: [
          ["ratio_s", "factor_s"],
          ["ratio_t", "factor_t"],
          ["factor_s", "scale"],
          ["factor_t", "scale"],
          ["factor_s", "translation"],
          ["factor_t", "translation"],
        ],
        total_work: expect.any(String),
        primitive_invocations: {
          conjugate: "((p + 1)**2)**2",
          harmonic: "((p + 1)**2)**2",
        },
        unresolved: [],
        relationships_used: [{ name: "domain:n", relationship: "0 <= n <= p" }],
        unused_assumptions: [],
      },
      scenarios: [
        { name: "p12", substituted_work: "173760", unresolved: [] },
        { name: "p20", substituted_work: "1176632", unresolved: [] },
      ],
    });
    const system = (result.details as { system: { equations: unknown[] } })
      .system;
    const translation = system.equations.find(
      (item) => (item as { name?: string }).name === "translation",
    );
    expect(translation).toMatchObject({
      name: "translation",
      interpretation: {
        normalized_sympy:
          "Eq(L[n, m], a[n]*Sum(b[k]*Sum(harmonic(k + n, l + m)*conjugate(M[k, l]), (l, -k, k)), (k, 0, p)))",
      },
      operation_counts: {
        additions: 2,
        subtractions: 0,
        multiplications: 4,
        divisions: 0,
        powers: 0,
      },
      aggregate_operation_counts: {
        additions: "(p + (p + 1)*(3*p + 2))*(p + 1)**2",
        subtractions: "0",
        multiplications: "((p + 1)*(p + 2) + 1)*(p + 1)**2",
        divisions: "0",
        powers: "0",
      },
      aggregate_work:
        "(p + (p + 1)*(3*p + 2))*(p + 1)**2 + ((p + 1)*(p + 2) + 1)*(p + 1)**2 + 2*((p + 1)**2)**2",
      dependencies: ["factor_s", "factor_t"],
      primitive_invocations: {
        conjugate: "((p + 1)**2)**2",
        harmonic: "((p + 1)**2)**2",
      },
      unknown_costs: [],
      unresolved: [],
      relationships_used: [{ name: "domain:n", relationship: "0 <= n <= p" }],
    });
  });

  it("round trips a query-bearing AFMM tail through the registered tool", async () => {
    const current = host();
    const adapter = fileURLToPath(
      new URL("../bridge/formula_adapter.py", import.meta.url),
    );
    await start(
      current.api,
      Promise.resolve({
        ready: true,
        command: "uv",
        args: ["run", "--locked", "python", adapter],
      }),
    );
    const result = await current.tools[0]!.execute("id", afmmTailParameters);
    expect(result.details).toMatchObject({
      status: "success",
      abstract_work: null,
      direct_work_applicability: "not_finite",
      queries: [
        {
          name: "afmm_tail",
          kind: "closed_form",
          answers: [
            {
              conclusion: "proved_under_assumptions",
              evidence: {
                kind: "closed_form",
                verification: "infinite_partial_sum",
              },
              derived_candidates: [expect.any(Object)],
            },
          ],
        },
      ],
    });
  });

  it("feeds a verified closed form into later registered-tool queries", async () => {
    const current = host();
    const adapter = fileURLToPath(
      new URL("../bridge/formula_adapter.py", import.meta.url),
    );
    await start(
      current.api,
      Promise.resolve({
        ready: true,
        command: "uv",
        args: ["run", "--locked", "python", adapter],
      }),
    );
    const result = await current.tools[0]!.execute("id", {
      expression: "Sum(k * 2**k, (k, 0, 3))",
      queries: [
        { name: "closed", kind: "closed_form" },
        {
          name: "same",
          kind: "equivalence",
          target: { kind: "derived", query: "closed" },
          comparison: "34",
        },
        {
          name: "constant_limit",
          kind: "limit",
          target: { kind: "derived", query: "closed" },
          variable: "x",
          point: "oo",
        },
      ],
    });
    expect(result.details).toMatchObject({
      status: "success",
      queries: [
        { name: "closed", kind: "closed_form" },
        {
          name: "same",
          kind: "equivalence",
          target: { kind: "derived", query: "closed" },
          normalized_target: { normalized_sympy: "34" },
          answers: [{ conclusion: "proved_under_assumptions" }],
        },
        {
          name: "constant_limit",
          kind: "limit",
          target: { kind: "derived", query: "closed" },
          normalized_target: { normalized_sympy: "34" },
          answers: [{ conclusion: "proved_under_assumptions" }],
        },
      ],
    });
    expect(result.content[0]?.text).toContain(
      "- same (equivalence): proved_under_assumptions",
    );
    expect(result.content[0]?.text).toContain(
      "- constant_limit (limit): proved_under_assumptions",
    );
  });

  it("round trips a partial nested polynomial candidate through the registered tool", async () => {
    const current = host();
    const adapter = fileURLToPath(
      new URL("../bridge/formula_adapter.py", import.meta.url),
    );
    await start(
      current.api,
      Promise.resolve({
        ready: true,
        command: "uv",
        args: ["run", "--locked", "python", adapter],
      }),
    );
    const result = await current.tools[0]!.execute("id", {
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
        {
          name: "sign",
          kind: "properties",
          target: { kind: "derived", query: "closed" },
          checks: [{ kind: "sign" }],
        },
        {
          name: "growth",
          kind: "asymptotic",
          target: { kind: "derived", query: "closed" },
          variable: "p",
          point: "oo",
          order: 2,
        },
      ],
    });
    expect(result.details).toMatchObject({
      status: "success",
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
        {
          name: "sign",
          kind: "properties",
          target: { kind: "derived", query: "closed" },
          answers: [{ conclusion: "proved" }],
        },
        {
          name: "growth",
          kind: "asymptotic",
          target: { kind: "derived", query: "closed" },
          answers: [{ conclusion: "proved_under_assumptions" }],
        },
      ],
    });
    expect(result.content[0]?.text).toContain("- closed (closed_form): proved");
    expect(result.content[0]?.text).toContain("(p + 1)**2");
  });

  it("accepts equation-local constraint uses introduced by a derived consumer", async () => {
    const current = host();
    const adapter = fileURLToPath(
      new URL("../bridge/formula_adapter.py", import.meta.url),
    );
    await start(
      current.api,
      Promise.resolve({
        ready: true,
        command: "uv",
        args: ["run", "--locked", "python", adapter],
      }),
    );
    const result = await current.tools[0]!.execute("id", {
      equations: [
        {
          name: "count",
          expression: "Eq(C[p], Sum(Sum(p, (l, 0, 0)), (k, 0, 3)))",
          domains: { p: { lower: "-5", upper: "5" } },
          constraints: [
            {
              name: "nonnegative",
              relationship: "p >= 0",
              target: "p",
            },
          ],
        },
      ],
      queries: [
        {
          name: "closed",
          kind: "closed_form",
          target: { kind: "equation", name: "count" },
        },
        {
          name: "sign",
          kind: "properties",
          target: { kind: "derived", query: "closed" },
          checks: [{ kind: "sign" }],
        },
      ],
    });
    expect(result.details).toMatchObject({
      status: "success",
      queries: [
        {
          name: "closed",
          answers: [{ conclusion: "proved", constraint_uses: [] }],
        },
        {
          name: "sign",
          target: { kind: "derived", query: "closed" },
          answers: [
            {
              conclusion: "proved_under_assumptions",
              constraint_uses: [
                {
                  equation: "count",
                  name: "nonnegative",
                  target: "p",
                  relationship: "p >= 0",
                },
              ],
            },
          ],
        },
      ],
    });
  });

  it("surfaces Python request diagnostics through the registered tool", async () => {
    const current = host();
    const adapter = fileURLToPath(
      new URL("../bridge/formula_adapter.py", import.meta.url),
    );
    await start(
      current.api,
      Promise.resolve({
        ready: true,
        command: "uv",
        args: ["run", "--locked", "python", adapter],
      }),
    );
    const invalidParameters = {
      expression: "x",
      queries: [
        {
          name: "missing_direction",
          kind: "limit",
          variable: "x",
          point: "0",
        },
      ],
    } as unknown as FormulaParameters;
    expect(Value.Check(current.tools[0]!.parameters, invalidParameters)).toBe(
      true,
    );
    await expect(
      current.tools[0]!.execute("id", invalidParameters),
    ).rejects.toMatchObject({
      kind: "request",
      message: expect.stringMatching(
        /queries\.0\.limit[\s\S]*finite points require direction/,
      ),
    });
  });

  it("discovers the product skill only with the ready analysis tool", async () => {
    const ready = host();
    await start(
      ready.api,
      Promise.resolve({ ready: true, command: "unused", args: [] }),
    );
    const readyResources = await ready.events.get("resources_discover")?.(
      {},
      context(false),
    );
    expect(readyResources).toEqual({
      skillPaths: [expect.stringMatching(/packages\/pi-science\/skills$/)],
    });

    const disabled = host();
    await start(
      disabled.api,
      Promise.resolve({ ready: false, diagnosis: "uv is missing" }),
    );
    expect(
      await disabled.events.get("resources_discover")?.({}, context(false)),
    ).toBeUndefined();
  });

  it("warns once per disabled extension instance through UI and keeps doctor", async () => {
    const current = host();
    await start(
      current.api,
      Promise.resolve({ ready: false, diagnosis: "uv is missing" }),
    );
    expect(current.tools).toHaveLength(0);
    const notifyContext = context(true);
    const sessionStart = current.events.get("session_start");
    await sessionStart?.({}, notifyContext);
    await sessionStart?.({}, notifyContext);
    expect(notifyContext.ui.notify).toHaveBeenCalledOnce();

    const doctor = current.commands.get("pi-science-doctor");
    await doctor?.handler("", notifyContext);
    expect(notifyContext.ui.notify).toHaveBeenLastCalledWith(
      expect.stringContaining("Reload or restart"),
      "warning",
    );
  });

  it("uses stderr without UI and a new ready instance recovers", async () => {
    const stderr = vi
      .spyOn(process.stderr, "write")
      .mockImplementation(() => true);
    try {
      const disabled = host();
      await start(
        disabled.api,
        Promise.resolve({ ready: false, diagnosis: "provisioning failed" }),
      );
      await disabled.events.get("session_start")?.({}, context(false));
      await disabled.commands
        .get("pi-science-doctor")
        ?.handler("", context(false));
      expect(stderr).toHaveBeenCalled();

      const recovered = host();
      await start(
        recovered.api,
        Promise.resolve({ ready: true, command: "unused", args: [] }),
      );
      expect(recovered.tools).toHaveLength(1);
    } finally {
      stderr.mockRestore();
    }
  });

  it("derives the full commit and origin from the installed repository checkout", async () => {
    expect(resolvePinnedRevision(repositoryRoot)).toMatch(/^[0-9a-f]{40}$/);
    expect(resolvePinnedSource(repositoryRoot)).toEqual({
      revision: expect.stringMatching(/^[0-9a-f]{40}$/),
      repo: expect.stringContaining("pi-science"),
    });
    const nonRepository = await mkdtemp(join(tmpdir(), "pi-science-no-git-"));
    try {
      expect(resolvePinnedRevision(nonRepository)).toBeUndefined();
      expect(resolvePinnedSource(nonRepository)).toBeUndefined();
    } finally {
      await rm(nonRepository, { recursive: true, force: true });
    }
  });
});
