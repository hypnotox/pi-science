import { EventEmitter } from "node:events";
import { readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AnalysisRequest } from "../src/bridge.js";
import {
  appendResponseChunk,
  BridgeError,
  invokeAdapter,
  MAX_FORMULA_BYTES,
  MAX_RESPONSE_BYTES,
  PROTOCOL_VERSION,
} from "../src/bridge.js";
import { afmmRequest, afmmTotalWork } from "./afmm-fixture.js";

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
  direct_work_applicability: "finite",
  direct_work_blockers: [],
  scenarios: [],
  queries: [],
};
const richSuccess = {
  ...success,
  interpretation: {
    normalized_sympy: "Sum(x[i] + 1, (i, 0, n - 1))",
    normalized_latex: "sum",
  },
  operation_counts: {
    ...success.operation_counts,
    additions: 1,
    subtractions: 1,
  },
  abstract_work: 2,
  direct_work_applicability: "finite",
  direct_work_blockers: [],
  system: {
    equations: [
      {
        name: "expression",
        interpretation: success.interpretation,
        operation_counts: success.operation_counts,
        aggregate_operation_counts: {
          additions: "Max(0, n - 1) + Max(0, n)",
          subtractions: "0",
          multiplications: "0",
          divisions: "0",
          powers: "0",
        },
        aggregate_work: "Max(0, n - 1) + Max(0, n)",
        direct_work_applicability: "finite",
        direct_work_blockers: [],
        dependencies: [],
        primitive_invocations: {},
        unknown_costs: [],
        unresolved: [],
        relationships_used: [],
      },
    ],
    aggregate_operation_counts: {
      additions: "Max(0, n - 1) + Max(0, n)",
      subtractions: "0",
      multiplications: "0",
      divisions: "0",
      powers: "0",
    },
    total_work: "Max(0, n - 1) + Max(0, n)",
    direct_work_applicability: "finite",
    direct_work_blockers: [],
    dependency_edges: [],
    reuse: [],
    primitive_invocations: {},
    unknown_costs: [],
    unresolved: [],
    extraction_opportunities: [],
    relationships_used: [],
    unused_assumptions: [],
  },
  scenarios: [
    {
      name: "bounded",
      substituted_work: "N + 1",
      choice_work: { "p=2": "N + 1" },
      asymptotic: "Theta(N)",
      interval: {
        lower: "1",
        upper: "10",
        lower_inclusive: true,
        upper_inclusive: true,
        lower_work: "2",
        upper_work: "11",
        infimum: "2",
        supremum: "11",
        infimum_attained: true,
        supremum_attained: true,
        conservative: true,
      },
      substitutions: { p: "2" },
      relationships_used: [
        { name: "population", relationship: "Sum(n[b], (b, 0, B - 1)) == N" },
      ],
      qualifications: ["under declared positive integer domains"],
      unresolved: [],
    },
  ],
};
const responder = (result: unknown = success) =>
  script(
    `process.stdin.resume();process.stdin.on("end",()=>process.stdout.write(${JSON.stringify(
      JSON.stringify({ version: PROTOCOL_VERSION, result }),
    )}))`,
  );
const exitingResponder = (envelope: unknown, code = 2) =>
  script(
    `process.stdin.resume();process.stdin.on("end",()=>process.stdout.write(${JSON.stringify(
      JSON.stringify(envelope),
    )},()=>process.exit(${code})))`,
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
    await expect(
      invokeAdapter("uv", args, request("Sum(x[i] + 1, (i, 0, n - 1))")),
    ).resolves.toMatchObject({
      status: "success",
      system: {
        equations: [{ name: "expression" }],
        dependency_edges: [],
      },
    });
    await expect(
      invokeAdapter("uv", args, request("oo")),
    ).resolves.toMatchObject({
      status: "success",
      abstract_work: null,
      direct_work_applicability: "not_finite",
      system: {
        aggregate_operation_counts: null,
        total_work: null,
        primitive_invocations: null,
        equations: [
          {
            aggregate_operation_counts: null,
            aggregate_work: null,
            primitive_invocations: null,
          },
        ],
      },
    });
    const system = await invokeAdapter("uv", args, afmmRequest);
    expect(system).toMatchObject({
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
  });

  it("preserves Python request validation diagnostics from the real adapter", async () => {
    const adapter = fileURLToPath(
      new URL("../bridge/formula_adapter.py", import.meta.url),
    );
    const invalidRequest = {
      syntax: "sympy",
      expression: "x",
      queries: [
        {
          name: "missing_direction",
          kind: "limit",
          variable: "x",
          point: "0",
        },
      ],
    } as unknown as AnalysisRequest;

    await expect(
      invokeAdapter(
        "uv",
        ["run", "--locked", "python", adapter],
        invalidRequest,
      ),
    ).rejects.toMatchObject({
      kind: "request",
      message: expect.stringMatching(
        /queries\.0\.limit[\s\S]*finite points require direction/,
      ),
    });
  });

  it.each([
    ["ASCII", "x".repeat(4_096)],
    ["multibyte UTF-8", "é".repeat(2_048)],
  ])(
    "preserves a request diagnostic at the exact byte bound for %s",
    async (_name, message) => {
      await expect(
        invokeAdapter(
          node,
          exitingResponder({
            version: PROTOCOL_VERSION,
            error: { kind: "request", message },
          }),
          request(),
        ),
      ).rejects.toMatchObject({ kind: "request", message });
    },
  );

  it.each([
    ["success envelope", { version: PROTOCOL_VERSION, result: success }, 2],
    [
      "wrong exit status",
      {
        version: PROTOCOL_VERSION,
        error: { kind: "request", message: "validation failed" },
      },
      3,
    ],
    [
      "wrong protocol version",
      {
        version: PROTOCOL_VERSION - 1,
        error: { kind: "request", message: "bad" },
      },
      2,
    ],
    [
      "surplus envelope key",
      {
        version: PROTOCOL_VERSION,
        error: { kind: "request", message: "bad" },
        extra: true,
      },
      2,
    ],
    [
      "surplus error key",
      {
        version: PROTOCOL_VERSION,
        error: { kind: "request", message: "bad", extra: true },
      },
      2,
    ],
    [
      "wrong error kind",
      {
        version: PROTOCOL_VERSION,
        error: { kind: "internal", message: "bad" },
      },
      2,
    ],
    [
      "empty request diagnostic",
      {
        version: PROTOCOL_VERSION,
        error: { kind: "request", message: "" },
      },
      2,
    ],
    [
      "oversized request diagnostic",
      {
        version: PROTOCOL_VERSION,
        error: { kind: "request", message: "x".repeat(4_097) },
      },
      2,
    ],
    [
      "oversized multibyte request diagnostic",
      {
        version: PROTOCOL_VERSION,
        error: { kind: "request", message: "é".repeat(2_049) },
      },
      2,
    ],
  ])(
    "keeps non-exact request error %s as a process failure",
    async (_name, envelope, code) => {
      await kind(
        invokeAdapter(node, exitingResponder(envelope, code), request()),
        "process",
      );
    },
  );

  it("keeps malformed request-error output as a process failure", async () => {
    await kind(
      invokeAdapter(
        node,
        script(
          'process.stdin.resume();process.stdin.on("end",()=>process.stdout.write("not json",()=>process.exit(2)))',
        ),
        request(),
      ),
      "process",
    );
    await kind(
      invokeAdapter(
        node,
        script(
          "process.stdin.resume();process.stdin.on('end',()=>process.stdout.write(Buffer.from([255]),()=>process.exit(2)))",
        ),
        request(),
      ),
      "process",
    );
  });

  it("accepts complete diagnostics and rejects missing, surplus, and malformed nested fields", async () => {
    const failure = {
      status: "failure",
      error: {
        code: "malformed_syntax",
        message: "bad",
        location: { line: 1, column: 0 },
        source: {
          path: "expression",
          span: { start: { line: 1, column: 0 }, end: { line: 1, column: 1 } },
          excerpt: "x",
        },
        supported_alternative: null,
      },
    };
    await expect(
      invokeAdapter(node, responder(failure), request()),
    ).resolves.toMatchObject(failure);
    const missing = { ...failure, error: { ...failure.error } };
    delete (missing.error as { source?: unknown }).source;
    const surplus = { ...failure, error: { ...failure.error, extra: true } };
    const malformed = {
      ...failure,
      error: {
        ...failure.error,
        source: { ...failure.error.source, span: { start: 1, end: 2 } },
      },
    };
    const mismatchedLocation = {
      ...failure,
      error: { ...failure.error, location: { line: 1, column: 1 } },
    };
    const reversedSpan = {
      ...failure,
      error: {
        ...failure.error,
        source: {
          ...failure.error.source,
          span: {
            start: { line: 2, column: 0 },
            end: { line: 1, column: 0 },
          },
        },
        location: { line: 2, column: 0 },
      },
    };
    const oversizedDiagnostic = {
      ...failure,
      error: {
        ...failure.error,
        source: { ...failure.error.source, excerpt: "x".repeat(161) },
      },
    };
    for (const value of [
      missing,
      surplus,
      malformed,
      mismatchedLocation,
      reversedSpan,
      oversizedDiagnostic,
    ])
      await kind(invokeAdapter(node, responder(value), request()), "protocol");
  });

  it("strictly validates populated protocol-v6 query result unions", async () => {
    const identityAnswer = {
      check: null,
      conclusion: "proved",
      conditions: [],
      assumptions_used: [],
      relevant_unsupported_assumptions: [],
      blockers: [],
      evidence: {
        kind: "identity",
        statement: "normalized difference is zero",
      },
      derived_candidates: [],
    };
    const query = {
      name: "same",
      kind: "equivalence",
      target: { kind: "expression" },
      normalized_target: success.interpretation,
      summary: "equivalence comparison",
      answers: [identityAnswer],
    };
    const populated = { ...success, queries: [query] };
    const equivalenceRequest = {
      ...request(),
      queries: [
        { name: "same", kind: "equivalence" as const, comparison: "x" },
      ],
    };
    await expect(
      invokeAdapter(node, responder(populated), equivalenceRequest),
    ).resolves.toMatchObject(populated);

    const counterexample = {
      ...query,
      name: "different",
      answers: [
        {
          ...identityAnswer,
          conclusion: "disproved",
          evidence: {
            kind: "counterexample",
            substitutions: { x: "1/2" },
            target_value: "1/2",
            comparison_value: "0",
          },
        },
      ],
    };
    const futureEvidence = [
      {
        ...query,
        name: "closed",
        kind: "closed_form",
        answers: [
          {
            ...identityAnswer,
            evidence: {
              kind: "closed_form",
              verification: "finite_antidifference",
              statement: "n*(n+1)/2",
            },
          },
        ],
      },
      {
        ...query,
        name: "properties",
        kind: "properties",
        answers: [
          {
            ...identityAnswer,
            check: { kind: "sign" },
            evidence: {
              kind: "property",
              value: "positive",
              intervals: ["(0, oo)"],
            },
          },
        ],
      },
      {
        ...query,
        name: "limit",
        kind: "limit",
        answers: [
          {
            ...identityAnswer,
            evidence: {
              kind: "limit",
              exists: false,
              value: null,
              left: "-oo",
              right: "oo",
            },
          },
        ],
      },
      {
        ...query,
        name: "asymptotic",
        kind: "asymptotic",
        answers: [
          {
            ...identityAnswer,
            evidence: { kind: "asymptotic", statement: "x", remainder: null },
          },
        ],
      },
    ];
    await expect(
      invokeAdapter(
        node,
        responder({ ...success, queries: [counterexample, ...futureEvidence] }),
        {
          ...request(),
          queries: [
            { name: "different", kind: "equivalence", comparison: "0" },
            { name: "closed", kind: "closed_form" },
            {
              name: "properties",
              kind: "properties",
              checks: [{ kind: "sign" as const }],
            },
            {
              name: "limit",
              kind: "limit",
              variable: "x",
              point: "0",
              direction: "both",
            },
            {
              name: "asymptotic",
              kind: "asymptotic",
              variable: "x",
              point: "oo",
              order: 1,
            },
          ],
        },
      ),
    ).resolves.toMatchObject({ queries: [counterexample, ...futureEvidence] });

    const unresolved = {
      ...query,
      name: "later",
      kind: "closed_form",
      answers: [
        {
          ...identityAnswer,
          conclusion: "unresolved",
          blockers: ["query kind is not implemented in this release slice"],
          evidence: null,
        },
      ],
    };
    await expect(
      invokeAdapter(node, responder({ ...success, queries: [unresolved] }), {
        ...request(),
        queries: [{ name: "later", kind: "closed_form" }],
      }),
    ).resolves.toMatchObject({ queries: [unresolved] });

    const invalid = [
      { ...query, name: "not-valid" },
      {
        ...query,
        answers: [{ ...identityAnswer, conclusion: "not_proved" }],
      },
      { ...query, name: "x".repeat(129) },
      { ...query, name: "oo" },
      { ...query, target: { kind: "expression", extra: true } },
      { ...query, target: { kind: "equation" } },
      { ...query, target: { kind: "equation", name: "not-valid" } },
      { ...query, target: { kind: "equation", name: "x".repeat(129) } },
      { ...query, answers: [{ ...identityAnswer, check: undefined }] },
      { ...query, answers: [identityAnswer, identityAnswer] },
      {
        ...query,
        answers: [
          {
            ...identityAnswer,
            evidence: { ...identityAnswer.evidence, extra: true },
          },
        ],
      },
      {
        ...query,
        answers: [
          {
            ...identityAnswer,
            evidence: {
              kind: "limit",
              exists: true,
              value: "0",
              left: "0",
              right: "0",
            },
          },
        ],
      },
      ...["zoo", "nan", "2/4"].map((targetValue) => ({
        ...counterexample,
        answers: [
          {
            ...counterexample.answers[0],
            evidence: {
              ...counterexample.answers[0].evidence,
              target_value: targetValue,
            },
          },
        ],
      })),
      {
        ...counterexample,
        answers: [
          {
            ...counterexample.answers[0],
            evidence: {
              ...counterexample.answers[0].evidence,
              substitutions: { x: "-0" },
            },
          },
        ],
      },
      {
        ...counterexample,
        answers: [
          {
            ...counterexample.answers[0],
            evidence: {
              ...counterexample.answers[0].evidence,
              substitutions: { x: "2/4" },
            },
          },
        ],
      },
      {
        ...counterexample,
        answers: [
          {
            ...counterexample.answers[0],
            evidence: {
              ...counterexample.answers[0].evidence,
              substitutions: { "not-valid": "1" },
            },
          },
        ],
      },
      {
        ...counterexample,
        answers: [
          {
            ...counterexample.answers[0],
            evidence: {
              ...counterexample.answers[0].evidence,
              substitutions: { x: "9".repeat(1025) },
            },
          },
        ],
      },
      {
        ...counterexample,
        answers: [
          {
            ...counterexample.answers[0],
            evidence: {
              ...counterexample.answers[0].evidence,
              substitutions: Object.fromEntries(
                Array.from({ length: 257 }, (_, index) => [`x${index}`, "1"]),
              ),
            },
          },
        ],
      },
      {
        ...query,
        answers: [
          {
            ...identityAnswer,
            assumptions_used: Array.from({ length: 129 }, (_, index) => ({
              name: `a${index}`,
              relationship: "x > 0",
            })),
          },
        ],
      },
      {
        ...futureEvidence[1],
        answers: [futureEvidence[1].answers[0], futureEvidence[1].answers[0]],
      },
      {
        ...futureEvidence[1],
        answers: [
          {
            ...futureEvidence[1].answers[0],
            check: { kind: "valid_domain", variable: "not-valid" },
          },
        ],
      },
      {
        ...unresolved,
        answers: [
          {
            ...unresolved.answers[0],
            derived_candidates: [
              {
                interpretation: success.interpretation,
                operation_counts: success.operation_counts,
                abstract_work: 0,
              },
            ],
          },
        ],
      },
    ];
    for (const malformedQuery of invalid)
      await kind(
        invokeAdapter(
          node,
          responder({ ...success, queries: [malformedQuery] }),
          request(),
        ),
        "protocol",
      );
  });

  it("correlates query responses with the submitted query request", async () => {
    const query = {
      name: "domain",
      kind: "properties",
      target: { kind: "expression" },
      normalized_target: success.interpretation,
      summary: "properties",
      answers: [
        {
          check: { kind: "sign" },
          conclusion: "unresolved",
          conditions: [],
          assumptions_used: [],
          relevant_unsupported_assumptions: [],
          blockers: ["unsupported"],
          evidence: null,
          derived_candidates: [],
        },
      ],
    };
    const requestWithQuery = {
      ...request(),
      queries: [
        {
          name: "domain",
          kind: "properties" as const,
          checks: [{ kind: "sign" as const }],
        },
      ],
    };
    await expect(
      invokeAdapter(
        node,
        responder({ ...success, queries: [query] }),
        requestWithQuery,
      ),
    ).resolves.toMatchObject({ queries: [query] });
    const systemRequest = {
      syntax: "sympy" as const,
      equations: [{ name: "stage", expression: "Eq(y, x)" }],
      queries: [
        {
          name: "domain",
          kind: "properties" as const,
          target: { kind: "equation" as const, name: "stage" },
          checks: [{ kind: "valid_domain" as const, variable: "x" }],
        },
      ],
    };
    const reorderedSystemQuery = {
      ...query,
      target: { name: "stage", kind: "equation" as const },
      answers: [
        {
          ...query.answers[0],
          check: { variable: "x", kind: "valid_domain" as const },
        },
      ],
    };
    await expect(
      invokeAdapter(
        node,
        responder({ ...richSuccess, queries: [reorderedSystemQuery] }),
        systemRequest,
      ),
    ).resolves.toMatchObject({ queries: [reorderedSystemQuery] });
    for (const response of [
      { ...success, queries: [] },
      { ...success, queries: [{ ...query, name: "other" }] },
      { ...success, queries: [{ ...query, kind: "closed_form" }] },
      {
        ...success,
        queries: [{ ...query, target: { kind: "equation", name: "q" } }],
      },
      {
        ...success,
        queries: [
          {
            ...query,
            answers: [
              {
                ...query.answers[0],
                check: { kind: "valid_domain", variable: "x" },
              },
            ],
          },
        ],
      },
    ])
      await kind(
        invokeAdapter(node, responder(response), requestWithQuery),
        "protocol",
      );
    await kind(
      invokeAdapter(node, responder({ ...success, queries: [query] }), {
        ...requestWithQuery,
        expression: undefined,
      } as unknown as AnalysisRequest),
      "protocol",
    );
    await kind(
      invokeAdapter(node, responder(success), systemRequest),
      "protocol",
    );
  });

  it("strictly correlates finite and non-finite direct-work variants", async () => {
    const invalid = [
      { ...success, abstract_work: null },
      {
        ...success,
        direct_work_applicability: "not_finite",
        direct_work_blockers: ["blocked"],
      },
      {
        ...richSuccess,
        system: {
          ...richSuccess.system,
          equations: [
            {
              ...richSuccess.system.equations[0],
              direct_work_applicability: "not_finite",
              direct_work_blockers: ["blocked"],
            },
          ],
        },
      },
      {
        ...richSuccess,
        system: {
          ...richSuccess.system,
          total_work: null,
          aggregate_operation_counts: null,
          primitive_invocations: null,
        },
      },
      {
        ...richSuccess,
        abstract_work: null,
        direct_work_applicability: "not_finite",
        direct_work_blockers: ["blocked"],
      },
      {
        ...richSuccess,
        system: {
          ...richSuccess.system,
          aggregate_operation_counts: null,
          total_work: null,
          direct_work_applicability: "not_finite",
          direct_work_blockers: ["blocked"],
          primitive_invocations: null,
        },
      },
      {
        ...richSuccess,
        system: {
          ...richSuccess.system,
          equations: [
            {
              ...richSuccess.system.equations[0],
              aggregate_operation_counts: null,
              aggregate_work: null,
              direct_work_applicability: "not_finite",
              direct_work_blockers: ["blocked"],
              primitive_invocations: null,
            },
          ],
        },
      },
    ];
    for (const value of invalid)
      await kind(invokeAdapter(node, responder(value), request()), "protocol");
  });

  it("strictly rejects malformed envelopes and result shapes", async () => {
    const outputs = [
      "no",
      JSON.stringify(null),
      JSON.stringify([]),
      JSON.stringify({ version: 1, result: success }),
      JSON.stringify({ version: 3, result: success, extra: true }),
      JSON.stringify({ version: 3, result: null }),
      JSON.stringify({ version: 3, result: [] }),
      JSON.stringify({ version: 3, result: { status: "success" } }),
      JSON.stringify({
        version: 3,
        result: { ...success, unexpected: true },
      }),
      JSON.stringify({
        version: 3,
        result: {
          ...richSuccess,
          system: { ...richSuccess.system, extra: true },
        },
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

  it("rejects duplicate response keys and invalid UTF-8", async () => {
    const duplicateRoot = `{"version":3,"version":3,"result":${JSON.stringify(success)}}`;
    const duplicateNested = `{"version":3,"result":{"status":"failure","error":{"code":"invalid_system","code":"invalid_system","message":"bad"}}}`;
    for (const output of [duplicateRoot, duplicateNested])
      await kind(
        invokeAdapter(
          node,
          script(`process.stdout.write(${JSON.stringify(output)})`),
          request(),
        ),
        "malformed-output",
      );
    await kind(
      invokeAdapter(
        node,
        script("process.stdout.write(Buffer.from([0x7b,0xff,0x7d]))"),
        request(),
      ),
      "malformed-output",
    );
  });

  const setSystemField = (
    value: typeof richSuccess,
    field: string,
    replacement: unknown,
  ): void => {
    (value.system as Record<string, unknown>)[field] = replacement;
  };
  it.each([
    [
      "equation counts",
      (value: typeof richSuccess) => {
        value.system.equations[0].operation_counts.additions = -1;
      },
    ],
    [
      "equation dependencies",
      (value: typeof richSuccess) => {
        (value.system.equations[0] as Record<string, unknown>).dependencies = [
          1,
        ];
      },
    ],
    [
      "aggregate count shape",
      (value: typeof richSuccess) => {
        delete (
          value.system.aggregate_operation_counts as Record<string, unknown>
        ).powers;
      },
    ],
    [
      "dependency edge shape",
      (value: typeof richSuccess) => {
        setSystemField(value, "dependency_edges", [["producer"]]);
      },
    ],
    [
      "reuse count",
      (value: typeof richSuccess) => {
        setSystemField(value, "reuse", [
          { producer: "a", consumer: "b", references: 0 },
        ]);
      },
    ],
    [
      "primitive map",
      (value: typeof richSuccess) => {
        setSystemField(value, "primitive_invocations", { f: 1 });
      },
    ],
    [
      "unknown array",
      (value: typeof richSuccess) => {
        setSystemField(value, "unknown_costs", [false]);
      },
    ],
    [
      "relationship provenance",
      (value: typeof richSuccess) => {
        setSystemField(value, "relationships_used", [
          { name: "missing-source" },
        ]);
      },
    ],
    [
      "unused assumptions",
      (value: typeof richSuccess) => {
        setSystemField(value, "unused_assumptions", [1]);
      },
    ],
    [
      "scenario qualification",
      (value: typeof richSuccess) => {
        (value.scenarios[0] as Record<string, unknown>).qualifications = [1];
      },
    ],
    [
      "scenario interval",
      (value: typeof richSuccess) => {
        (value.scenarios[0].interval as Record<string, unknown>).conservative =
          "yes";
      },
    ],
  ])("fails closed for malformed rich response %s", async (_name, mutate) => {
    const result = structuredClone(richSuccess);
    mutate(result);
    await kind(invokeAdapter(node, responder(result), request()), "protocol");
  });

  it("bounds expressions by UTF-8 bytes while permitting empty and boundary input", async () => {
    await expect(
      invokeAdapter(node, responder(), request("")),
    ).resolves.toEqual(success);
    const boundary = "é".repeat(MAX_FORMULA_BYTES / 2);
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

  it("bounds equivalence operands before starting the adapter", async () => {
    await kind(
      invokeAdapter(node, responder(), {
        syntax: "sympy",
        expression: "x",
        queries: [
          {
            name: "too_large",
            kind: "equivalence",
            comparison: "x".repeat(MAX_FORMULA_BYTES + 1),
          },
        ],
      }),
      "protocol",
    );
  });

  it("rejects aggregate and escape-heavy envelopes that exceed the adapter byte bound", async () => {
    await kind(
      invokeAdapter(node, responder(), {
        syntax: "sympy",
        expression: "x",
        assumptions: Array.from({ length: 40 }, (_, index) => ({
          name: `a${index}`,
          relationship: "x".repeat(MAX_FORMULA_BYTES),
        })),
      }),
      "protocol",
    );
    await kind(
      invokeAdapter(node, responder(), request("\u0000".repeat(400_000))),
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
