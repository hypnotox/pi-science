import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import type {
  ExtensionAPI,
  ExtensionContext,
} from "@earendil-works/pi-coding-agent";
import type { TSchema } from "typebox";
import formulaSchemaJson from "./formula-schema.json" with { type: "json" };
import {
  invokeAdapter,
  type BridgeResult,
  type ExpressionAnalysisRequest,
  type SystemAnalysisRequest,
} from "./bridge.js";
import { provision, type Readiness } from "./provision.js";

const SHA = /^[0-9a-f]{40}$/;
const PRODUCT_SKILLS = fileURLToPath(new URL("../skills", import.meta.url));
export const formulaSchema = structuredClone(formulaSchemaJson) as TSchema;
export type FormulaParameters =
  | Omit<ExpressionAnalysisRequest, "syntax">
  | Omit<SystemAnalysisRequest, "syntax">;

export type PinnedSource = { revision: string; repo: string };

export function resolvePinnedSource(
  repositoryRoot: string,
  git = "git",
): PinnedSource | undefined {
  try {
    const revision = execFileSync(
      git,
      ["-C", repositoryRoot, "rev-parse", "--verify", "HEAD^{commit}"],
      { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] },
    ).trim();
    const repo = execFileSync(
      git,
      ["-C", repositoryRoot, "config", "--get", "remote.origin.url"],
      { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] },
    ).trim();
    return SHA.test(revision) && repo ? { revision, repo } : undefined;
  } catch {
    return undefined;
  }
}

export function resolvePinnedRevision(
  repositoryRoot: string,
  git = "git",
): string | undefined {
  return resolvePinnedSource(repositoryRoot, git)?.revision;
}

const MAX_COMPACT_DERIVED_CANDIDATES = 3;
const MAX_COMPACT_EXPRESSION_LENGTH = 512;

function compactExpression(expression: string): string {
  return expression.length <= MAX_COMPACT_EXPRESSION_LENGTH
    ? expression
    : `${expression.slice(0, MAX_COMPACT_EXPRESSION_LENGTH - 3)}...`;
}

function compactToolText(result: BridgeResult): string {
  if (result.status === "failure")
    return [
      "Interpretation",
      "- unavailable",
      "Query conclusions",
      "- none",
      "Work",
      "- unavailable",
      "Blockers",
      `- ${result.error.message}`,
    ].join("\n");

  const queryConclusions = result.queries.flatMap((query) =>
    query.answers.map((answer) => {
      const check = answer.check
        ? `; ${answer.check.kind}${"variable" in answer.check ? ` (${answer.check.variable})` : ""}`
        : "";
      const derived =
        query.kind === "closed_form" &&
        (answer.conclusion === "proved" ||
          answer.conclusion === "proved_under_assumptions")
          ? answer.derived_candidates
              .slice(0, MAX_COMPACT_DERIVED_CANDIDATES)
              .map((candidate) =>
                compactExpression(candidate.interpretation.normalized_sympy),
              )
          : [];
      return `- ${query.name} (${query.kind}${check}): ${answer.conclusion}${derived.length === 0 ? "" : `; derived: ${derived.join(", ")}`}`;
    }),
  );
  const generalWork = result.system?.total_work ?? result.abstract_work;
  const work = [
    `- General direct work: ${generalWork ?? "unavailable"}`,
    ...(result.scenarios.length === 0
      ? ["- Specialized evaluation work: none"]
      : result.scenarios.map(
          (scenario) =>
            `- Specialized evaluation work (scenario ${scenario.name}): ${scenario.substituted_work}`,
        )),
  ];
  const blockers = [
    ...result.direct_work_blockers,
    ...(result.system?.unknown_costs.map((cost) => `unknown cost: ${cost}`) ??
      []),
    ...(result.system?.unresolved ?? []),
    ...result.scenarios.flatMap((scenario) =>
      scenario.unresolved.map(
        (blocker) => `scenario ${scenario.name}: ${blocker}`,
      ),
    ),
    ...result.queries.flatMap((query) =>
      query.answers.flatMap((answer) =>
        answer.blockers.map((blocker) => `query ${query.name}: ${blocker}`),
      ),
    ),
  ];
  return [
    "Interpretation",
    `- SymPy: ${result.interpretation.normalized_sympy}`,
    `- LaTeX: ${result.interpretation.normalized_latex}`,
    "Query conclusions",
    ...(queryConclusions.length === 0 ? ["- none"] : queryConclusions),
    "Work",
    ...work,
    "Blockers",
    ...(blockers.length === 0
      ? ["- none"]
      : blockers.map((blocker) => `- ${blocker}`)),
  ].join("\n");
}

function toolResult(result: BridgeResult) {
  return {
    content: [{ type: "text" as const, text: compactToolText(result) }],
    details: result,
  };
}

function report(context: ExtensionContext, text: string, ready: boolean): void {
  if (context.hasUI) context.ui.notify(text, ready ? "info" : "warning");
  else process.stderr.write(`pi-science: ${text}\n`);
}

export async function start(
  pi: ExtensionAPI,
  readiness: Promise<Readiness>,
): Promise<void> {
  const state = await readiness;
  pi.registerCommand("pi-science-doctor", {
    description:
      "Show formula analysis readiness and reload/restart recovery guidance",
    handler: async (_args, context) => {
      const text = state.ready
        ? "Formula analysis is ready."
        : `${state.diagnosis} Reload or restart Pi to retry provisioning.`;
      report(context, text, state.ready);
    },
  });

  if (!state.ready) {
    let warned = false;
    pi.on("session_start", async (_event, context) => {
      if (warned) return;
      warned = true;
      report(
        context,
        `${state.diagnosis} Reload or restart Pi to retry provisioning.`,
        false,
      );
    });
    return;
  }

  pi.on("resources_discover", () => ({ skillPaths: [PRODUCT_SKILLS] }));

  pi.registerTool({
    name: "analyze_formula",
    label: "Analyze formula",
    description:
      "Analyze one restricted SymPy expression or named equation system with bounded nested finite-work and acyclic affine output-domain analysis",
    promptSnippet:
      "Analyze restricted-SymPy formulas for normalized interpretation and qualified symbolic work with nested binders and dependent affine output domains",
    promptGuidelines: [
      "Before first using analyze_formula, read the available pi-science-formula-analysis skill for the accepted dialect, request modeling, and result interpretation.",
      "When analyze_formula rejects a request, use its Python-owned message and any returned path, span, or supported alternative to correct the request.",
    ],
    parameters: formulaSchema,
    async execute(_id, params: FormulaParameters, signal) {
      const result = await invokeAdapter(
        state.command,
        state.args,
        { syntax: "sympy", ...params },
        10_000,
        signal,
      );
      return toolResult(result);
    },
  });
}

export default async function extension(pi: ExtensionAPI): Promise<void> {
  const repositoryRoot = fileURLToPath(new URL("../../../", import.meta.url));
  const adapter = fileURLToPath(
    new URL("../bridge/formula_adapter.py", import.meta.url),
  );
  const source = resolvePinnedSource(repositoryRoot);
  await start(
    pi,
    provision({
      revision: source?.revision ?? "",
      repo: source?.repo ?? "",
      adapter,
      checkoutRoot: repositoryRoot,
    }),
  );
}
