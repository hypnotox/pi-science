import { mkdtemp } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import type { TSchema } from "typebox";
import { Value } from "typebox/value";
import { describe, expect, it, vi } from "vitest";
import {
  type FormulaParameters,
  resolvePinnedRevision,
  resolvePinnedSource,
  start,
} from "../src/index.js";
import { afmmParameters, afmmTotalWork } from "./afmm-fixture.js";

const repositoryRoot = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "../../..",
);

type Command = {
  handler(args: string, context: unknown): Promise<void>;
};
type Tool = {
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
  it("uses the real command signature and registers a valid tool result", async () => {
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
      scenarios: [],
    };
    await start(
      current.api,
      Promise.resolve({
        ready: true,
        command: process.execPath,
        args: [
          "-e",
          `process.stdin.resume();process.stdin.on("end",()=>process.stdout.write(${JSON.stringify(
            JSON.stringify({ version: 2, result: response }),
          )}))`,
        ],
      }),
    );
    expect(current.commands.has("pi-science-doctor")).toBe(true);
    expect(current.tools).toHaveLength(1);
    const parameters = current.tools[0]!.parameters;
    expect(Value.Check(parameters, { expression: "x" })).toBe(true);
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
    for (const invalid of [
      {},
      { expression: "x", equations: [{ name: "a", expression: "Eq(a, x)" }] },
      { equations: [] },
      { expression: "x", syntax: "latex" },
      { expression: "x", extra: true },
      {
        expression: "x",
        scenarios: [
          { name: "unsafe", fixed: { N: Number.MAX_SAFE_INTEGER + 1 } },
        ],
      },
      { equations: [{ name: "a", expression: "Eq(a, x)", extra: true }] },
    ])
      expect(Value.Check(parameters, invalid)).toBe(false);
    const result = await current.tools[0]?.execute("id", { expression: "x" });
    expect(result).toEqual({
      content: [{ type: "text", text: JSON.stringify(response) }],
      details: response,
    });
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
    expect(result.content).toEqual([
      { type: "text", text: JSON.stringify(result.details) },
    ]);
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
    expect(resolvePinnedRevision(nonRepository)).toBeUndefined();
    expect(resolvePinnedSource(nonRepository)).toBeUndefined();
  });
});
