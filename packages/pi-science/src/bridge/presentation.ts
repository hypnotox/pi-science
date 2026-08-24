import type {
  AnalysisSuccess,
  BridgeResult,
  OptimizationResult,
} from "./results.js";

const MAX_COMPACT_DERIVED_CANDIDATES = 3;
const MAX_COMPACT_EXPRESSION_LENGTH = 512;

function compactExpression(expression: string): string {
  return expression.length <= MAX_COMPACT_EXPRESSION_LENGTH
    ? expression
    : `${expression.slice(0, MAX_COMPACT_EXPRESSION_LENGTH - 3)}...`;
}

function compactOptimization(result: OptimizationResult): string {
  const plans = result.plans.flatMap((plan, index) => {
    const computation =
      plan.candidate.expression ??
      plan.candidate.equations
        .map((equation) => equation.expression)
        .join("; ");
    const replay = plan.trace
      .map(
        (step, stepIndex) =>
          `${stepIndex + 1}. ${step.kind} [tier ${step.tier}] (${step.transformations
            .map((item) =>
              item.target.kind === "expression"
                ? "expression"
                : `equation ${item.target.name}`,
            )
            .join(", ")})`,
      )
      .join(" → ");
    return [
      `- Plan ${index + 1}: ${replay}; outputs: ${plan.candidate.outputs.join(", ")}`,
      `  Candidate: ${compactExpression(computation)}`,
      `  strict_improvement: ${plan.claim.proof_policy}; ${plan.claim.semantics}; ${plan.claim.work_semantics}; objective ${plan.claim.objective.kind}`,
    ];
  });
  const scope = result.search_scope;
  return [
    "Optimization",
    "Classification",
    `- ${result.classification}`,
    "Plans",
    ...(plans.length ? plans : ["- none"]),
    "Deterministic ranked prefix",
    `- ${result.selection.kind}; projection limit ${result.selection.projection_limit}`,
    "Search scope",
    `- ${scope.policy}; depth ${scope.monotonic_depth}; families: ${scope.families.join(", ")}; engine: ${scope.engine}; completion: ${scope.completion}`,
    ...(scope.qualifications.length
      ? scope.qualifications.map((qualification) => `- ${qualification}`)
      : ["- none"]),
    "Output projection",
    `- ${result.projection_status}; projection limit ${result.projection_limit}`,
    ...(result.projection_qualifications.length
      ? result.projection_qualifications.map(
          (qualification) => `- ${qualification}`,
        )
      : ["- none"]),
    "Blockers",
    ...(result.blockers.length
      ? result.blockers.map(
          (blocker) =>
            `- missing information: ${blocker.required_information}; ${blocker.reason}; ${blocker.family}; ${blocker.target}`,
        )
      : ["- none"]),
  ].join("\n");
}

function compactToolText(result: BridgeResult): string {
  if (result.status === "failure") {
    if (typeof result.error === "string")
      return ["Optimization", "Failure", `- ${result.error}`].join("\n");
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
  }

  if (result.status === "success" && "classification" in result)
    return compactOptimization(result);

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

  const analysis = result as AnalysisSuccess;
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
    "Blockers",
    ...(blockers.length === 0
      ? ["- none"]
      : blockers.map((blocker) => `- ${blocker}`)),
  ].join("\n");
}

export function toolResult(result: BridgeResult) {
  return {
    content: [{ type: "text" as const, text: compactToolText(result) }],
    details: result,
  };
}
