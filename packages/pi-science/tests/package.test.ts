import { execFileSync } from "node:child_process";
import { mkdtemp, readFile, readdir, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";
import { describe, expect, it } from "vitest";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");
const bridgeModules = [
  "protocol",
  "requests",
  "results",
  "diagnostics",
  "correlation",
  "client",
  "presentation",
] as const;
const bridgeExports = [
  "PROTOCOL_VERSION",
  "MAX_FORMULA_BYTES",
  "MAX_ENVELOPE_BYTES",
  "MAX_RESPONSE_BYTES",
  "MathematicalDomain",
  "IndexDomain",
  "VariableDeclaration",
  "DomainConstraint",
  "EquationRequest",
  "FunctionDefinition",
  "PrimitiveCost",
  "Assumption",
  "DirectedDefinition",
  "ExactScenarioScalar",
  "OptimizationObjectiveInput",
  "AlgorithmicOptimizationFamily",
  "OptimizationConfig",
  "IntervalBound",
  "Scenario",
  "EquationTarget",
  "DerivedTarget",
  "PropertyCheckRequest",
  "ExpressionQueryRequest",
  "SystemQueryRequest",
  "QueryRequest",
  "ExpressionAnalysisRequest",
  "SystemAnalysisRequest",
  "AnalysisRequest",
  "CandidateComputation",
  "CandidateTarget",
  "CandidateOutputMapping",
  "CandidateComparisonRequest",
  "DominanceRange",
  "DominanceRequest",
  "OptimizeRequest",
  "FormulaRequest",
  "Interpretation",
  "OperationCounts",
  "SymbolicOperationCounts",
  "RelationshipUse",
  "SourceLocation",
  "SourceSpan",
  "SourceReference",
  "DirectWorkApplicability",
  "EffectiveIndexDomain",
  "ConstraintUse",
  "EquationEffectiveDomains",
  "EquationReport",
  "ScenarioResult",
  "SystemReport",
  "OptimizationSuggestion",
  "OptimizationCandidate",
  "OptimizationObjective",
  "OptimizationTraceStep",
  "OptimizationPlan",
  "OptimizationReport",
  "AnalysisSuccess",
  "ResolvedTarget",
  "PropertyCheck",
  "DerivedCandidate",
  "QueryAnswer",
  "QueryResult",
  "AnalysisFailure",
  "CandidateAnalysisSuccess",
  "CandidateAnalysisReport",
  "CandidateComparisonSuccess",
  "DominanceTerm",
  "DominanceCell",
  "DominanceSuccess",
  "OptimizationOperationSuccess",
  "OptimizationOperationFailure",
  "OptimizationOperationResult",
  "BridgeResult",
  "appendResponseChunk",
  "BridgeFailureKind",
  "BridgeError",
  "decodeUtf8Strict",
  "parseStrictJson",
  "invokeAdapter",
] as const;

function moduleSpecifiers(source: string): string[] {
  const parsed = ts.createSourceFile(
    "probe.ts",
    source,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TS,
  );
  const specifiers: string[] = [];
  const visit = (node: ts.Node): void => {
    if (
      (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) &&
      node.moduleSpecifier !== undefined &&
      ts.isStringLiteral(node.moduleSpecifier)
    )
      specifiers.push(node.moduleSpecifier.text);
    if (
      ts.isCallExpression(node) &&
      (node.expression.kind === ts.SyntaxKind.ImportKeyword ||
        (ts.isIdentifier(node.expression) &&
          node.expression.text === "require")) &&
      node.arguments.length === 1 &&
      ts.isStringLiteral(node.arguments[0])
    )
      specifiers.push(node.arguments[0].text);
    ts.forEachChild(node, visit);
  };
  visit(parsed);
  return [...new Set(specifiers)].sort();
}

async function typescriptSources(
  directory: string,
): Promise<Array<{ path: string; source: string }>> {
  const entries = await readdir(directory, { withFileTypes: true });
  const sources = await Promise.all(
    entries.map(async (entry) => {
      const path = join(directory, entry.name);
      if (entry.isDirectory()) return typescriptSources(path);
      if (!entry.isFile() || !entry.name.endsWith(".ts")) return [];
      return [{ path, source: await readFile(path, "utf8") }];
    }),
  );
  return sources.flat();
}

function isBridgeBarrelSpecifier(specifier: string): boolean {
  return /(^|\/)bridge(?:\.(?:js|ts))?$/.test(specifier);
}

function namedExports(source: string): string[] {
  const parsed = ts.createSourceFile(
    "bridge.ts",
    source,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TS,
  );
  return parsed.statements
    .filter(ts.isExportDeclaration)
    .flatMap((declaration) =>
      declaration.exportClause !== undefined &&
      ts.isNamedExports(declaration.exportClause)
        ? declaration.exportClause.elements.map((element) => element.name.text)
        : [],
    );
}

describe("npm package boundary", () => {
  it("preserves the exact bridge compatibility surface", async () => {
    const source = await readFile(
      join(root, "packages/pi-science/src/bridge.ts"),
      "utf8",
    );
    expect(namedExports(source).sort()).toEqual([...bridgeExports].sort());
    expect(Object.keys(await import("../src/bridge.js")).sort()).toEqual(
      [
        "PROTOCOL_VERSION",
        "MAX_FORMULA_BYTES",
        "MAX_ENVELOPE_BYTES",
        "MAX_RESPONSE_BYTES",
        "appendResponseChunk",
        "decodeUtf8Strict",
        "parseStrictJson",
        "BridgeError",
        "invokeAdapter",
      ].sort(),
    );
  });

  it("keeps bridge children on the declared dependency graph", async () => {
    const sources = await Promise.all(
      bridgeModules.map((name) =>
        readFile(
          join(root, `packages/pi-science/src/bridge/${name}.ts`),
          "utf8",
        ),
      ),
    );
    const allowed = {
      protocol: ["node:util"],
      requests: [],
      results: ["./protocol.js", "./requests.js"],
      diagnostics: ["./protocol.js"],
      correlation: [
        "./diagnostics.js",
        "./protocol.js",
        "./requests.js",
        "./results.js",
      ],
      client: [
        "../process.js",
        "./correlation.js",
        "./diagnostics.js",
        "./protocol.js",
        "./requests.js",
        "./results.js",
      ],
      presentation: ["./results.js"],
    } satisfies Record<(typeof bridgeModules)[number], string[]>;
    const edges = Object.fromEntries(
      bridgeModules.map((name, index) => [
        name,
        moduleSpecifiers(sources[index]),
      ]),
    ) as Record<(typeof bridgeModules)[number], string[]>;
    for (const name of bridgeModules) {
      const permitted: readonly string[] = allowed[name];
      expect(edges[name].filter((edge) => !permitted.includes(edge))).toEqual(
        [],
      );
    }
    expect(edges.client).toEqual(
      expect.arrayContaining(["../process.js", "./correlation.js"]),
    );
    expect(sources[bridgeModules.indexOf("correlation")]).toMatch(
      /export function validateCorrelatedResult\(/,
    );
  });

  it("keeps production integration on owning bridge modules", async () => {
    const sourceRoot = join(root, "packages/pi-science/src");
    const sources = await typescriptSources(sourceRoot);
    for (const { path, source } of sources) {
      if (path === join(sourceRoot, "bridge.ts")) continue;
      expect(
        moduleSpecifiers(source).filter(isBridgeBarrelSpecifier),
        path,
      ).toEqual([]);
    }

    const [index, provision] = await Promise.all(
      ["index", "provision"].map((name) =>
        readFile(join(sourceRoot, `${name}.ts`), "utf8"),
      ),
    );
    expect(moduleSpecifiers(index)).toEqual(
      expect.arrayContaining([
        "./bridge/client.js",
        "./bridge/presentation.js",
        "./bridge/requests.js",
      ]),
    );
    expect(moduleSpecifiers(provision)).toContain("./bridge/protocol.js");
  });

  it("recognizes direct compatibility-barrel specifiers without children", () => {
    expect(
      [
        "./bridge.js",
        "../bridge",
        "/tmp/packages/pi-science/src/bridge.ts",
        "pi-science/packages/pi-science/src/bridge.js",
      ].filter(isBridgeBarrelSpecifier),
    ).toHaveLength(4);
    expect(isBridgeBarrelSpecifier("./bridge/client.js")).toBe(false);
  });

  it("detects static, re-exported, required, and dynamic module edges", () => {
    expect(
      moduleSpecifiers(`
        import "../bridge";
        export { value } from "/tmp/index.ts";
        require("pi-science/packages/pi-science/src/bridge.js");
        import("../index.js");
      `),
    ).toEqual([
      "../bridge",
      "../index.js",
      "/tmp/index.ts",
      "pi-science/packages/pi-science/src/bridge.js",
    ]);
  });
  it("ships one complete uniquely named readiness-gated formula skill", async () => {
    const skill = await readFile(
      join(root, "packages/pi-science/skills/formula-analysis/SKILL.md"),
      "utf8",
    );
    expect(skill).toContain("name: pi-science-formula-analysis");
    expect(skill).toContain("analyze_formula");
    expect(skill).toContain("do not include `syntax` in a tool call");
    expect(skill).toContain("Sum(body, (index, lower, upper))");
    expect(skill).toContain("Parser acceptance, request-context validity");
    expect(skill).toContain("any returned field path, source span");
    expect(skill).toContain("proof qualifications");
    expect(skill).toContain("partial direct `closed_form` support");
    expect(skill).toContain("Sum(Sum(1, (l, -k, k)), (k, 0, p))");
    expect(skill).toContain(
      "distinct from the partial nested mathematical closed-form family",
    );
    expect(skill).toContain("compact human-readable projection");
    expect(skill).toContain("complete canonical report in `details`");
    expect(skill).toContain("complete replayable plans");
    expect(skill).toContain("selected one- or two-step optimization plan");
    expect(skill).toContain(
      "Keep plans atomic and do not combine separate candidates",
    );
    expect(skill).not.toContain("best proved");
    expect(skill).toContain("every ordered family step");
    expect(skill).toContain(
      "Canonical `details` contains every complete replayable trace candidate",
    );
    expect(skill).toContain(
      "evaluation work, not represented mathematical value",
    );
    expect(skill).toMatch(/unresolved query blocker[\s\S]+recovery hint/);
    expect(skill).toMatch(/Recovery hints[\s\S]+do not certify equivalence/);
    expect(skill).toMatch(
      /Recovery hints[\s\S]+do not[\s\S]+promise wider evaluator support/,
    );
    expect(skill).toContain("py_science.formula");
    expect(skill).toContain("PEP 723");
    expect(skill).not.toContain("pi_science");
  });

  it("packs the required Pi sources under AGPL and production-installs externally", async () => {
    const directory = await mkdtemp(join(tmpdir(), "pi-science-pack-"));
    let installed: string | undefined;
    try {
      const packed = execFileSync(
        "npm",
        ["pack", "--json", "--pack-destination", directory],
        { cwd: root, encoding: "utf8" },
      );
      const tarball = join(directory, JSON.parse(packed)[0].filename as string);
      const files = execFileSync("tar", ["-tzf", tarball], { encoding: "utf8" })
        .trim()
        .split("\n");
      expect(files).toEqual(
        expect.arrayContaining([
          "package/package.json",
          "package/packages/pi-science/src/index.ts",
          "package/packages/pi-science/src/formula-schema.json",
          "package/packages/pi-science/src/bridge.ts",
          ...bridgeModules.map(
            (name) => `package/packages/pi-science/src/bridge/${name}.ts`,
          ),
          "package/packages/pi-science/src/provision.ts",
          "package/packages/pi-science/src/process.ts",
          "package/packages/pi-science/bridge/formula_adapter.py",
          "package/packages/pi-science/skills/formula-analysis/SKILL.md",
        ]),
      );
      expect(
        JSON.parse(
          execFileSync("tar", ["-xOzf", tarball, "package/package.json"], {
            encoding: "utf8",
          }).toString(),
        ).license,
      ).toBe("AGPL-3.0-only");
      installed = await mkdtemp(join(tmpdir(), "pi-science-install-"));
      execFileSync(
        "npm",
        ["install", "--omit=dev", "--ignore-scripts", tarball],
        { cwd: installed, stdio: "pipe" },
      );
      const probe = execFileSync(
        process.execPath,
        [
          "--input-type=module",
          "--eval",
          `
            import { createRequire } from "node:module";
            import { writeFileSync } from "node:fs";
            import { discoverAndLoadExtensions } from "@earendil-works/pi-coding-agent";
            import { resolve } from "node:path";
            const extensionPath = resolve("node_modules/pi-science/packages/pi-science/src/index.ts");
            const adapter = resolve("node_modules/pi-science/packages/pi-science/bridge/formula_adapter.py");
            const bridgeRoot = resolve("node_modules/pi-science/packages/pi-science/src/bridge");
            const bridgeBarrel = resolve("node_modules/pi-science/packages/pi-science/src/bridge.ts");
            const bridgeImports =
              "import { PROTOCOL_VERSION as BARREL_PROTOCOL_VERSION } from " +
              JSON.stringify(bridgeBarrel) + ";\\n" +
              "import { PROTOCOL_VERSION as CHILD_PROTOCOL_VERSION } from " +
              JSON.stringify(resolve(bridgeRoot, "protocol.ts")) + ";\\n" +
              ${JSON.stringify(["requests", "results", "diagnostics", "correlation", "client", "presentation"])}
                .map((name) => "import " + JSON.stringify(resolve(bridgeRoot, name + ".ts")) + ";\\n")
                .join("");
            const probeExtension = resolve("formula-probe.ts");
            writeFileSync(
              probeExtension,
              bridgeImports +
                "import { start } from " + JSON.stringify(extensionPath) + ";\\n" +
                "export default (pi) => { if (BARREL_PROTOCOL_VERSION !== 16 || CHILD_PROTOCOL_VERSION !== 16) throw new Error(\\\"installed bridge changed protocol version\\\"); return start(pi, Promise.resolve({ ready: true, command: \\\"uv\\\", args: [\\\"run\\\", \\\"--project\\\", " +
                JSON.stringify(${JSON.stringify(root)}) +
                ", \\\"--locked\\\", \\\"python\\\", " + JSON.stringify(adapter) + "] })); };\\n",
            );
            const loaded = await discoverAndLoadExtensions([probeExtension], process.cwd());
            if (loaded.errors.length !== 0) throw new Error(JSON.stringify(loaded.errors));
            if (loaded.extensions.length !== 1) throw new Error("formula extension was not loaded");
            const extension = loaded.extensions[0];
            if (!extension.commands.has("pi-science-doctor")) {
              throw new Error("formula extension did not register its diagnostic command");
            }
            const registered = extension.tools.get("analyze_formula");
            if (!registered) throw new Error("formula tool was not registered");
            const hostRequire = createRequire(import.meta.resolve("@earendil-works/pi-coding-agent"));
            const { Compile } = await import(hostRequire.resolve("typebox/compile"));
            const parameters = { expression: "x + 1", variables: { x: { domain: "real" } } };
            if (!Compile(registered.definition.parameters).Check(parameters)) {
              throw new Error("formula parameters failed host validation");
            }
            const result = await registered.definition.execute("id", parameters);
            if (result.details.status !== "success") {
              throw new Error("formula tool did not return success");
            }
            process.stdout.write("installed-formula-tool-invoked");
          `,
        ],
        { cwd: installed, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] },
      );
      expect(probe).toBe("installed-formula-tool-invoked");
    } finally {
      await rm(directory, { recursive: true, force: true });
      if (installed !== undefined)
        await rm(installed, { recursive: true, force: true });
    }
  }, 30_000);
});
