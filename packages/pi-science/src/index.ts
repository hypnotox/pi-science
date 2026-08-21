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
  type CandidateComparisonRequest,
  type ExpressionAnalysisRequest,
  type SystemAnalysisRequest,
  type DominanceRequest,
  type OptimizeRequest,
} from "./bridge.js";
import { provision, type Readiness } from "./provision.js";

const SHA = /^[0-9a-f]{40}$/;
const PRODUCT_SKILLS = fileURLToPath(new URL("../skills", import.meta.url));
export const formulaSchema = structuredClone(formulaSchemaJson) as TSchema;
export type FormulaParameters =
  | Omit<ExpressionAnalysisRequest, "syntax">
  | Omit<SystemAnalysisRequest, "syntax">
  | Omit<CandidateComparisonRequest, "syntax">
  | Omit<DominanceRequest, "syntax">
  | Omit<OptimizeRequest, "syntax">;

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

function objectiveProfile(
  objective: import("./bridge.js").OptimizationObjective,
): string {
  return objective.kind;
}

function compactToolText(result: BridgeResult): string {
  if (result.status === "failed")
    return ["Optimization", "- failed", "Blockers", `- ${result.error}`].join(
      "\n",
    );

  if (result.status === "success" && "search_status" in result) {
    const plans = result.plans.flatMap((plan, index) => {
      const computation =
        plan.candidate.expression ??
        plan.candidate.equations
          .map((equation) => equation.expression)
          .join("; ");
      return [
        `- Plan ${index + 1}: ${plan.suggestion.kind}; outputs: ${plan.candidate.outputs.join(", ")}`,
        `  Candidate: ${compactExpression(computation)}`,
        `  Objective profile: ${objectiveProfile(plan.objective)}`,
        `  Selected-objective savings: ${plan.suggestion.objective_savings}; ${plan.suggestion.finite_precision_qualification}`,
        ...(index === 0
          ? []
          : [
              `  Relation to previous: ${plan.suggestion.ordering.relation_to_previous === "previous_proved_superior" ? "previous plan proved superior" : "deterministic non-superiority tie-break"}`,
            ]),
      ];
    });
    return [
      "Optimization plans",
      ...(plans.length ? plans : ["- none"]),
      "Search status",
      `- ${result.search_status}`,
      "Qualifications",
      ...(result.qualifications.length
        ? result.qualifications.map((qualification) => `- ${qualification}`)
        : ["- none"]),
    ].join("\n");
  }

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

  if ("kind" in result && result.kind === "dominance_analysis") {
    const cellLabel = (cell: (typeof result.cells)[number]) =>
      "value" in cell ? cell.value : `${cell.lower} to ${cell.upper}`;
    const blockers = [
      ...result.blockers,
      ...result.cells.flatMap((cell) =>
        cell.blockers.map((blocker) => `${cellLabel(cell)}: ${blocker}`),
      ),
    ];
    return [
      "Axis",
      `- ${result.axis} (${result.axis_domain})`,
      "Effective domain",
      `- ${result.effective_range ? `${result.effective_range.lower}${result.effective_range.lower_inclusive ? " ≤" : " <"} ${result.axis} ${result.effective_range.upper_inclusive ? "≤" : "<"} ${result.effective_range.upper}` : "empty"}`,
      "Status",
      `- ${result.dominance_status}`,
      "Canonical signed terms",
      ...(result.terms.length
        ? result.terms.map((term) => `- ${term.id}: ${term.expression}`)
        : ["- none"]),
      "Dominant regions and ties",
      ...(result.cells.length
        ? result.cells.map(
            (cell) =>
              `- ${cellLabel(cell)}: ${cell.dominant.join(", ") || "unresolved"}`,
          )
        : ["- none"]),
      "Excluded poles",
      ...(result.exclusions.length
        ? result.exclusions.map((pole) => `- ${pole.value}`)
        : ["- none"]),
      "Never-dominant terms",
      ...(result.never_dominant.length
        ? result.never_dominant.map((term) => `- ${term}`)
        : ["- none"]),
      "Qualifications",
      ...(result.conditions.length
        ? result.conditions.map((condition) => `- ${condition}`)
        : ["- none"]),
      "Blockers",
      ...(blockers.length
        ? blockers.map((blocker) => `- ${blocker}`)
        : ["- none"]),
    ].join("\n");
  }

  if ("kind" in result && result.kind === "candidate_comparison") {
    const blockers = result.outputs.flatMap((output) =>
      output.answer.blockers.map((blocker) => `${output.name}: ${blocker}`),
    );
    const work = result.work_comparison;
    return [
      "Candidates and interpretations",
      ...result.candidates.map(
        (candidate) =>
          `- ${candidate.name}: ${candidate.analysis.interpretation.normalized_sympy}`,
      ),
      "Overall semantic status",
      `- ${result.semantic_status}`,
      "Mapped-output blockers",
      ...(blockers.length
        ? blockers.map((blocker) => `- ${blocker}`)
        : ["- none"]),
      "Aggregate work",
      `- Metric: ${work.metric}`,
      ...result.candidates.map(
        (candidate) =>
          `- ${candidate.name}: ${candidate.aggregate_work ?? "unavailable"}`,
      ),
      `- Delta (second - first): ${work.delta ?? "unavailable"}`,
      "Work decision",
      `- ${work.status}${work.conditions.length ? `; ${work.conditions.join("; ")}` : ""}`,
      "Unresolved costs",
      ...(work.blockers.length
        ? work.blockers.map((blocker) => `- ${blocker}`)
        : ["- none"]),
    ].join("\n");
  }

  const analysis = result as import("./bridge.js").AnalysisSuccess;
  const queryConclusions = analysis.queries.flatMap((query) =>
    query.answers.map((answer) => {
      const check = answer.check
        ? `; ${answer.check.kind}${"variable" in answer.check ? ` (${answer.check.variable})` : ""}`
        : "";
      const derived =
        query.target.kind === "derived" && query.normalized_target
          ? [compactExpression(query.normalized_target.normalized_sympy)]
          : query.kind === "closed_form" &&
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
  const generalWork = analysis.system?.total_work ?? analysis.abstract_work;
  const work = [
    `- General direct work: ${generalWork ?? "unavailable"}`,
    ...(analysis.scenarios.length === 0
      ? ["- Specialized evaluation work: none"]
      : analysis.scenarios.map(
          (scenario) =>
            `- Specialized evaluation work (scenario ${scenario.name}): ${scenario.substituted_work}`,
        )),
  ];
  const optimization = (() => {
    const report = analysis.optimization;
    if (report.status === "disabled") return [];

    if (report.suggestions.length === 0) {
      return [
        "Optimization advice",
        `- ${report.status === "complete" ? "no proved opportunity found within completed search" : "search incomplete; no proved suggestion was retained; inspect details for the local bound"}`,
        ...report.qualifications.map(
          (qualification) => `- qualification: ${qualification}`,
        ),
      ];
    }

    const suggestion = report.suggestions[0]!;
    const transformations = suggestion.transformations
      .map((transformation) => {
        const target =
          transformation.target.kind === "expression"
            ? "expression"
            : `equation ${transformation.target.name}`;
        return `${target}: ${transformation.original.normalized_sympy} → ${transformation.proposed.normalized_sympy}`;
      })
      .join("; ");
    const intermediate = suggestion.intermediate
      ? `; shared intermediate ${suggestion.intermediate.name} = ${suggestion.intermediate.expression.normalized_sympy}`
      : "";
    const conditions = suggestion.conditions.length
      ? `; conditions: ${suggestion.conditions.join(", ")}`
      : "";
    const assumptions = suggestion.assumptions_used.length
      ? `; assumptions used: ${suggestion.assumptions_used
          .map(
            (assumption) => `${assumption.name} (${assumption.relationship})`,
          )
          .join(", ")}`
      : "";
    const additional = report.suggestions.length - 1;
    return [
      "Optimization advice",
      `- optimization suggestion: ${suggestion.kind}: ${transformations}${intermediate}; objective ${objectiveProfile(report.plans[0]!.objective)}: ${suggestion.objective_before} → ${suggestion.objective_after}; saves ${suggestion.objective_savings}${conditions}${assumptions}; ${suggestion.finite_precision_qualification}`,
      ...(additional === 0
        ? []
        : [
            `- ${additional} additional proved suggestion${additional === 1 ? "" : "s"} in details`,
          ]),
      ...(report.status === "incomplete"
        ? ["- search incomplete; inspect details for the local bound"]
        : []),
      ...report.qualifications.map(
        (qualification) => `- qualification: ${qualification}`,
      ),
    ];
  })();
  const blockers = [
    ...analysis.direct_work_blockers,
    ...(analysis.system?.unknown_costs.map((cost) => `unknown cost: ${cost}`) ??
      []),
    ...(analysis.system?.unresolved ?? []),
    ...analysis.scenarios.flatMap((scenario) =>
      scenario.unresolved.map(
        (blocker) => `scenario ${scenario.name}: ${blocker}`,
      ),
    ),
    ...analysis.queries.flatMap((query) =>
      query.answers.flatMap((answer) =>
        answer.blockers.map((blocker) => `query ${query.name}: ${blocker}`),
      ),
    ),
  ];
  return [
    "Interpretation",
    `- SymPy: ${analysis.interpretation.normalized_sympy}`,
    `- LaTeX: ${analysis.interpretation.normalized_latex}`,
    "Query conclusions",
    ...(queryConclusions.length === 0 ? ["- none"] : queryConclusions),
    "Work",
    ...work,
    ...optimization,
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
      "Analyze or explicitly optimize one restricted SymPy expression or named equation system with bounded exact-symbolic replayable plans, compare two candidates, or identify bounded aggregate-work term dominance on one axis",
    promptSnippet:
      "Analyze or optimize restricted-SymPy formulas for qualified symbolic work and bounded replayable plans, candidate comparison, or bounded one-axis aggregate-work term dominance",
    promptGuidelines: [
      "Before first using analyze_formula, read the available pi-science-formula-analysis skill for the accepted dialect, request modeling, and result interpretation.",
      "When analyze_formula rejects a request, use its Python-owned message and any returned path, span, or supported alternative to correct the request.",
    ],
    parameters: formulaSchema,
    async execute(_id, params: FormulaParameters, signal) {
      const result = await invokeAdapter(
        state.command,
        state.args,
        { syntax: "sympy", ...params } as import("./bridge.js").FormulaRequest,
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
