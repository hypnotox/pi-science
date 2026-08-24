import type {
  MathematicalDomain,
  DomainConstraint,
  EquationRequest,
  PropertyCheckRequest,
  SystemQueryRequest,
  QueryRequest,
  ExpressionAnalysisRequest,
  AnalysisRequest,
  CandidateOutputMapping,
  CandidateComparisonRequest,
  DominanceRequest,
  OptimizeRequest,
  FormulaRequest,
} from "./requests.js";
import type {
  ConstraintUse,
  OptimizationSuggestion,
  OptimizationCandidate,
  OptimizationObjective,
  OptimizationPlan,
  AnalysisSuccess,
  PropertyCheck,
  QueryAnswer,
  QueryResult,
  AnalysisFailure,
  BridgeResult,
} from "./results.js";
import {
  validInterpretation,
  validOperationCounts,
  validStringArray,
  validDirectWorkVariant,
  validRelationshipUses,
  validScenarioResult,
  validSystemReport,
  validBoundedDiagnosticText,
  validSourceLocation,
  validSourceSpan,
  validDiagnosticLocationRelation,
  boundedQueryText,
  ordinaryIdentifier,
  validNullableQueryText,
  canonicalExactScalar,
  validQueryEvidence,
  validQueryAnswer,
  validQueryResult,
} from "./results.js";
import {
  MAX_RESPONSE_BYTES,
  isRecord,
  exactKeys,
  nonNegativeInteger,
  positiveInteger,
} from "./protocol.js";
import { MAX_DIAGNOSTIC_BYTES } from "./diagnostics.js";

function isExpressionRequest(
  request: AnalysisRequest,
): request is ExpressionAnalysisRequest {
  return request.expression !== undefined;
}
function samePropertyCheck(
  result: PropertyCheck | null,
  request: PropertyCheckRequest,
): boolean {
  return (
    result !== null &&
    result.kind === request.kind &&
    (result.kind === "sign" ||
      (request.kind !== "sign" && result.variable === request.variable))
  );
}
function sameConstraintUse(
  use: ConstraintUse,
  constraint: DomainConstraint,
  equation: string,
): boolean {
  return (
    use.equation === equation &&
    use.name === constraint.name &&
    use.target === constraint.target &&
    use.relationship === constraint.relationship
  );
}

function validQueryConstraintUses(
  request: AnalysisRequest,
  query: QueryRequest,
  result: QueryResult,
  results: QueryResult[],
  index: number,
): boolean {
  const uses = result.answers.flatMap((answer) => answer.constraint_uses);
  if (
    result.answers.some(
      (answer) =>
        answer.constraint_uses.length !==
        new Set(answer.constraint_uses.map((use) => JSON.stringify(use))).size,
    )
  )
    return false;
  if (isExpressionRequest(request)) return uses.length === 0;
  const target = "target" in query ? query.target : undefined;
  if (target?.kind === "equation") {
    const equation = request.equations.find(
      (item) => item.name === target.name,
    );
    return (
      equation !== undefined &&
      uses.every((use) =>
        (equation.constraints ?? []).some((constraint) =>
          sameConstraintUse(use, constraint, equation.name),
        ),
      )
    );
  }
  if (target?.kind === "derived") {
    const sourceIndex =
      request.queries?.findIndex((item) => item.name === target.query) ?? -1;
    const source =
      sourceIndex >= 0 && sourceIndex < index
        ? results[sourceIndex]
        : undefined;
    const sourceQuery =
      sourceIndex >= 0 && sourceIndex < index
        ? request.queries?.[sourceIndex]
        : undefined;
    const sourceUses =
      source?.answers.flatMap((answer) => answer.constraint_uses) ?? [];
    const sourceTarget =
      sourceQuery !== undefined && "target" in sourceQuery
        ? sourceQuery.target
        : undefined;
    const sourceEquation =
      sourceTarget?.kind === "equation"
        ? request.equations.find((item) => item.name === sourceTarget.name)
        : undefined;
    return uses.every(
      (use) =>
        sourceUses.some(
          (sourceUse) => JSON.stringify(use) === JSON.stringify(sourceUse),
        ) ||
        (sourceEquation?.constraints ?? []).some((constraint) =>
          sameConstraintUse(use, constraint, sourceEquation!.name),
        ),
    );
  }
  return uses.length === 0;
}

function validQueryCorrelation(
  request: AnalysisRequest,
  results: QueryResult[],
): boolean {
  const queries = request.queries ?? [];
  if (queries.length !== results.length) return false;
  return queries.every((query, index) => {
    const result = results[index];
    if (
      result === undefined ||
      result.name !== query.name ||
      result.kind !== query.kind
    )
      return false;
    if ("target" in query && query.target?.kind === "derived") {
      const sourceQuery = query.target.query;
      if (
        result.target.kind !== "derived" ||
        result.target.query !== sourceQuery
      )
        return false;
      if (result.normalized_target === null) {
        const sourceIndex = queries.findIndex(
          (candidate) => candidate.name === sourceQuery,
        );
        const sourceResult = results[sourceIndex];
        const sourceConclusion = sourceResult?.answers[0]?.conclusion;
        if (
          sourceIndex < 0 ||
          sourceIndex >= index ||
          sourceResult?.kind !== "closed_form" ||
          sourceConclusion === undefined ||
          !result.answers[0]?.blockers.includes(
            `derived target source ${sourceQuery} concluded ${sourceConclusion}`,
          )
        )
          return false;
      }
    } else if (isExpressionRequest(request)) {
      if (result.target.kind !== "expression") return false;
    } else {
      const target = (query as SystemQueryRequest).target;
      if (
        result.target.kind !== "equation" ||
        target.kind !== "equation" ||
        result.target.name !== target.name
      )
        return false;
    }
    return (
      (query.kind !== "properties" ||
        (result.answers.length === query.checks.length &&
          query.checks.every((check, checkIndex) =>
            samePropertyCheck(result.answers[checkIndex]?.check ?? null, check),
          ))) &&
      validQueryConstraintUses(request, query, result, results, index)
    );
  });
}

function validEffectiveDomainPopulation(
  value: unknown,
  submittedDomains: Record<string, unknown>,
): boolean {
  if (
    !Array.isArray(value) ||
    value.length !== Object.keys(submittedDomains).length
  )
    return false;
  const reported = value.map((domain) =>
    isRecord(domain) && typeof domain.index === "string" ? domain.index : null,
  );
  return (
    reported.every((index) => index !== null) &&
    new Set(reported).size === reported.length &&
    reported.every((index) => index in submittedDomains)
  );
}

function validEffectiveDomainCorrelation(
  value: unknown,
  equations: EquationRequest[],
): boolean {
  const submitted = equations;
  return (
    Array.isArray(value) &&
    value.length === submitted.length &&
    value.every(
      (entry, equationIndex) =>
        isRecord(entry) &&
        entry.equation === submitted[equationIndex]?.name &&
        validEffectiveDomainPopulation(
          entry.domains,
          submitted[equationIndex]?.domains ?? {},
        ),
    )
  );
}

function validSystemCorrelation(
  request: AnalysisRequest,
  system: unknown,
): boolean {
  if (
    isExpressionRequest(request) ||
    !isRecord(system) ||
    !Array.isArray(system.equations)
  )
    return isExpressionRequest(request);
  return (
    system.equations.length === request.equations.length &&
    system.equations.every(
      (equation, index) =>
        isRecord(equation) &&
        equation.name === request.equations[index]?.name &&
        JSON.stringify(equation.constraints) ===
          JSON.stringify(request.equations[index]?.constraints ?? []) &&
        validEffectiveDomainPopulation(
          equation.effective_domains,
          request.equations[index]?.domains ?? {},
        ),
    )
  );
}

function validScenarioCorrelation(
  request: AnalysisRequest,
  scenarios: unknown[],
): boolean {
  if (isExpressionRequest(request)) return true;
  return scenarios.every((scenario) => {
    if (!isRecord(scenario) || !isRecord(scenario.choice_work)) return false;
    const choiceKeys = Object.keys(scenario.choice_work);
    if (choiceKeys.length === 0)
      return validEffectiveDomainCorrelation(
        scenario.effective_domains,
        request.equations,
      );
    if (!isRecord(scenario.choice_effective_domains)) return false;
    const choiceEffectiveDomains = scenario.choice_effective_domains;
    return (
      Array.isArray(scenario.effective_domains) &&
      scenario.effective_domains.length === 0 &&
      choiceKeys.every((key) =>
        validEffectiveDomainCorrelation(
          choiceEffectiveDomains[key],
          request.equations,
        ),
      )
    );
  });
}

function validCandidateTarget(value: unknown): boolean {
  return (
    isRecord(value) &&
    ((value.kind === "expression" && exactKeys(value, ["kind"])) ||
      (value.kind === "equation" &&
        exactKeys(value, ["kind", "name"]) &&
        ordinaryIdentifier(value.name)))
  );
}

function validCandidateTargetReference(value: unknown): boolean {
  return (
    isRecord(value) &&
    exactKeys(value, ["candidate", "target"]) &&
    ordinaryIdentifier(value.candidate) &&
    validCandidateTarget(value.target)
  );
}

function validCandidateOutputComparison(value: unknown): boolean {
  if (
    !isRecord(value) ||
    !exactKeys(value, [
      "name",
      "targets",
      "interface_status",
      "expanded_interpretations",
      "answer",
    ]) ||
    !ordinaryIdentifier(value.name) ||
    !Array.isArray(value.targets) ||
    value.targets.length !== 2 ||
    !value.targets.every(validCandidateTargetReference) ||
    !["compatible", "incompatible", "unresolved"].includes(
      String(value.interface_status),
    ) ||
    !(
      value.expanded_interpretations === null ||
      (Array.isArray(value.expanded_interpretations) &&
        value.expanded_interpretations.length === 2 &&
        value.expanded_interpretations.every(validInterpretation))
    ) ||
    !validQueryAnswer(value.answer) ||
    !isRecord(value.answer)
  )
    return false;
  const answer = value.answer as QueryAnswer;
  if (
    answer.check !== null ||
    answer.derived_candidates.length !== 0 ||
    answer.constraint_uses.length !== 0
  )
    return false;
  if (value.interface_status === "incompatible")
    return (
      value.expanded_interpretations === null &&
      answer.conclusion === "inapplicable" &&
      answer.blockers.length > 0 &&
      answer.evidence === null
    );
  if (value.interface_status === "unresolved")
    return (
      value.expanded_interpretations === null &&
      answer.conclusion === "unresolved" &&
      answer.blockers.length > 0 &&
      answer.evidence === null
    );
  if (value.expanded_interpretations === null)
    return (
      answer.conclusion === "unresolved" &&
      answer.blockers.length > 0 &&
      answer.evidence === null
    );
  if (
    answer.conclusion === "proved" ||
    answer.conclusion === "proved_under_assumptions"
  )
    return isRecord(answer.evidence) && answer.evidence.kind === "identity";
  if (answer.conclusion === "disproved")
    return (
      isRecord(answer.evidence) && answer.evidence.kind === "counterexample"
    );
  return (
    answer.conclusion === "unresolved" &&
    answer.blockers.length > 0 &&
    answer.evidence === null
  );
}

function validCandidateWorkComparison(value: unknown): boolean {
  if (
    !isRecord(value) ||
    !exactKeys(value, [
      "metric",
      "candidate_names",
      "candidate_works",
      "delta",
      "status",
      "conditions",
      "assumptions_used",
      "relevant_unsupported_assumptions",
      "blockers",
      "evidence",
    ]) ||
    value.metric !== "aggregate_abstract_work" ||
    !Array.isArray(value.candidate_names) ||
    value.candidate_names.length !== 2 ||
    !value.candidate_names.every(ordinaryIdentifier) ||
    new Set(value.candidate_names).size !== 2 ||
    !Array.isArray(value.candidate_works) ||
    value.candidate_works.length !== 2 ||
    !value.candidate_works.every(validNullableQueryText) ||
    !validNullableQueryText(value.delta) ||
    ![
      "not_comparable",
      "equal",
      "first_lower",
      "second_lower",
      "crossover",
      "unresolved",
    ].includes(String(value.status)) ||
    !validStringArray(value.conditions) ||
    value.conditions.length > 256 ||
    !value.conditions.every(boundedQueryText) ||
    !validRelationshipUses(value.assumptions_used) ||
    (value.assumptions_used as unknown[]).length > 128 ||
    !validStringArray(value.relevant_unsupported_assumptions) ||
    value.relevant_unsupported_assumptions.length > 128 ||
    !value.relevant_unsupported_assumptions.every(boundedQueryText) ||
    !validStringArray(value.blockers) ||
    value.blockers.length > 128 ||
    !value.blockers.every(boundedQueryText) ||
    !(value.evidence === null || validQueryEvidence(value.evidence))
  )
    return false;
  const finite = value.candidate_works.every((work) => work !== null);
  if (!finite && value.delta !== null) return false;
  if (value.status === "not_comparable")
    return value.blockers.length > 0 && value.evidence === null;
  if (value.status === "unresolved")
    return (
      value.blockers.length > 0 &&
      value.evidence === null &&
      (!finite || value.delta !== null)
    );
  if (!finite || value.delta === null || value.blockers.length > 0)
    return false;
  if (value.status === "equal")
    return isRecord(value.evidence) && value.evidence.kind === "identity";
  return isRecord(value.evidence) && value.evidence.kind === "property";
}

function mappedTargetsMatch(
  result: unknown[],
  requested: CandidateOutputMapping["targets"],
  candidateNames: string[],
): boolean {
  return candidateNames.every((name, index) => {
    const target = result[index];
    const submitted = requested.find((item) => item.candidate === name);
    return (
      isRecord(target) &&
      submitted !== undefined &&
      target.candidate === name &&
      JSON.stringify(target.target) === JSON.stringify(submitted.target)
    );
  });
}

function validComparisonResult(
  value: unknown,
  request: CandidateComparisonRequest,
): boolean {
  if (
    !isRecord(value) ||
    !exactKeys(value, [
      "kind",
      "status",
      "candidates",
      "outputs",
      "semantic_status",
      "work_comparison",
    ]) ||
    value.kind !== "candidate_comparison" ||
    value.status !== "success" ||
    !Array.isArray(value.candidates) ||
    value.candidates.length !== 2 ||
    !Array.isArray(value.outputs) ||
    value.outputs.length < 1 ||
    value.outputs.length > 32 ||
    !validCandidateWorkComparison(value.work_comparison)
  )
    return false;
  const names = request.candidates.map((candidate) => candidate.name);
  const reports = value.candidates;
  if (
    new Set(names).size !== 2 ||
    !names.every(ordinaryIdentifier) ||
    !reports.every((report, index) => {
      if (
        !isRecord(report) ||
        !exactKeys(report, ["name", "analysis", "aggregate_work"]) ||
        report.name !== names[index] ||
        !validNullableQueryText(report.aggregate_work) ||
        !isRecord(report.analysis)
      )
        return false;
      const analysis = { ...report.analysis };
      if (analysis.system === null) delete analysis.system;
      const candidate = request.candidates[index]!;
      const candidateRequest: AnalysisRequest =
        candidate.expression !== undefined
          ? {
              syntax: "sympy",
              expression: candidate.expression,
              variables: request.variables,
              functions: request.functions,
              primitive_costs: request.primitive_costs,
              assumptions: request.assumptions,
              definitions: request.definitions,
            }
          : {
              syntax: "sympy",
              equations: candidate.equations ?? [],
              variables: request.variables,
              functions: request.functions,
              primitive_costs: request.primitive_costs,
              assumptions: request.assumptions,
              definitions: request.definitions,
            };
      return (
        validResult(analysis, candidateRequest) &&
        analysis.status === "success" &&
        (analysis.direct_work_applicability === "finite") ===
          (report.aggregate_work !== null)
      );
    })
  )
    return false;
  const outputs = value.outputs;
  if (
    outputs.length !== request.outputs.length ||
    new Set(outputs.map((output) => (isRecord(output) ? output.name : null)))
      .size !== outputs.length ||
    !outputs.every((output, index) => {
      const mapped = request.outputs[index];
      return (
        mapped !== undefined &&
        validCandidateOutputComparison(output) &&
        isRecord(output) &&
        output.name === mapped.name &&
        Array.isArray(output.targets) &&
        mappedTargetsMatch(output.targets, mapped.targets, names)
      );
    })
  )
    return false;
  const work = value.work_comparison as Record<string, unknown>;
  if (
    JSON.stringify(work.candidate_names) !== JSON.stringify(names) ||
    !Array.isArray(work.candidate_works) ||
    !reports.every(
      (report, index) =>
        isRecord(report) &&
        (work.candidate_works as unknown[])[index] === report.aggregate_work,
    )
  )
    return false;
  const conclusions = outputs.map(
    (output) => (output as { answer: QueryAnswer }).answer.conclusion,
  );
  const semantic = conclusions.includes("disproved")
    ? "disproved"
    : conclusions.some(
          (item) => item === "unresolved" || item === "inapplicable",
        )
      ? "unresolved"
      : conclusions.includes("proved_under_assumptions")
        ? "proved_equal_under_assumptions"
        : "proved_equal";
  return (
    value.semantic_status === semantic &&
    (semantic === "proved_equal" ||
      semantic === "proved_equal_under_assumptions") !==
      (work.status === "not_comparable")
  );
}

type DominanceBoundary =
  | { kind: "negative_infinity" | "positive_infinity" }
  | { kind: "finite"; numerator: bigint; denominator: bigint };
type DominanceBounds = {
  lower: DominanceBoundary;
  upper: DominanceBoundary;
  lowerInclusive: boolean;
  upperInclusive: boolean;
};

function greatestCommonDivisor(left: bigint, right: bigint): bigint {
  let first = left < 0n ? -left : left;
  let second = right < 0n ? -right : right;
  while (second !== 0n) [first, second] = [second, first % second];
  return first;
}

function canonicalRequestExactScalar(value: unknown): string | null {
  if (typeof value === "string" && canonicalExactScalar(value)) return value;
  if (typeof value !== "string" && typeof value !== "number") return null;
  const text = String(value);
  const match = /^(-?)([0-9]+)(?:\.([0-9]+))?(?:[eE]([+-]?[0-9]+))?$/.exec(
    text,
  );
  if (match === null) return null;
  const fractionDigits = match[3]?.length ?? 0;
  const exponent = Number(match[4] ?? "0") - fractionDigits;
  if (!Number.isSafeInteger(exponent) || Math.abs(exponent) > 4096) return null;
  let numerator = BigInt(`${match[1]}${match[2]}${match[3] ?? ""}`);
  let denominator = 1n;
  if (exponent >= 0) numerator *= 10n ** BigInt(exponent);
  else denominator = 10n ** BigInt(-exponent);
  const divisor = greatestCommonDivisor(numerator, denominator);
  numerator /= divisor;
  denominator /= divisor;
  if (
    (numerator < 0n ? -numerator : numerator).toString(2).length > 3402 ||
    denominator.toString(2).length > 3402
  )
    return null;
  return denominator === 1n ? String(numerator) : `${numerator}/${denominator}`;
}

function dominanceBoundary(value: string): DominanceBoundary | null {
  if (value === "-oo") return { kind: "negative_infinity" };
  if (value === "oo") return { kind: "positive_infinity" };
  if (!canonicalExactScalar(value)) return null;
  const [numerator, denominator = "1"] = value.split("/");
  return {
    kind: "finite",
    numerator: BigInt(numerator!),
    denominator: BigInt(denominator),
  };
}

function compareDominanceBoundaries(
  left: DominanceBoundary,
  right: DominanceBoundary,
): -1 | 0 | 1 {
  if (left.kind === right.kind && left.kind !== "finite") return 0;
  if (left.kind === "negative_infinity" || right.kind === "positive_infinity")
    return -1;
  if (left.kind === "positive_infinity" || right.kind === "negative_infinity")
    return 1;
  if (left.kind !== "finite" || right.kind !== "finite") return 0;
  const difference =
    left.numerator * right.denominator - right.numerator * left.denominator;
  return difference < 0n ? -1 : difference > 0n ? 1 : 0;
}

function dominanceBounds(
  lowerText: string,
  upperText: string,
  lowerInclusive: boolean,
  upperInclusive: boolean,
): DominanceBounds | null {
  const lower = dominanceBoundary(lowerText);
  const upper = dominanceBoundary(upperText);
  if (
    lower === null ||
    upper === null ||
    lower.kind === "positive_infinity" ||
    upper.kind === "negative_infinity" ||
    (lower.kind === "negative_infinity" && lowerInclusive) ||
    (upper.kind === "positive_infinity" && upperInclusive)
  )
    return null;
  const comparison = compareDominanceBoundaries(lower, upper);
  if (
    comparison > 0 ||
    (comparison === 0 && !(lowerInclusive && upperInclusive))
  )
    return null;
  return { lower, upper, lowerInclusive, upperInclusive };
}

function dominanceRange(value: unknown): value is Record<string, unknown> {
  return (
    isRecord(value) &&
    exactKeys(value, [
      "lower",
      "upper",
      "lower_inclusive",
      "upper_inclusive",
    ]) &&
    typeof value.lower === "string" &&
    typeof value.upper === "string" &&
    typeof value.lower_inclusive === "boolean" &&
    typeof value.upper_inclusive === "boolean" &&
    dominanceBounds(
      value.lower,
      value.upper,
      value.lower_inclusive,
      value.upper_inclusive,
    ) !== null
  );
}

function sameDominanceRange(
  left: unknown,
  right: Record<string, unknown> | null,
): boolean {
  if (left === null || right === null) return left === right;
  return (
    isRecord(left) &&
    left.lower === right.lower &&
    left.upper === right.upper &&
    left.lower_inclusive === right.lower_inclusive &&
    left.upper_inclusive === right.upper_inclusive
  );
}

function dominanceRangeBounds(value: Record<string, unknown>): DominanceBounds {
  return dominanceBounds(
    value.lower as string,
    value.upper as string,
    value.lower_inclusive as boolean,
    value.upper_inclusive as boolean,
  )!;
}

function dominanceBoundsWithin(
  inner: DominanceBounds,
  outer: DominanceBounds,
): boolean {
  const lower = compareDominanceBoundaries(inner.lower, outer.lower);
  const upper = compareDominanceBoundaries(inner.upper, outer.upper);
  return (
    (lower > 0 ||
      (lower === 0 && (outer.lowerInclusive || !inner.lowerInclusive))) &&
    (upper < 0 ||
      (upper === 0 && (outer.upperInclusive || !inner.upperInclusive)))
  );
}

function dominancePointWithin(
  point: DominanceBoundary,
  range: DominanceBounds,
): boolean {
  const lower = compareDominanceBoundaries(point, range.lower);
  const upper = compareDominanceBoundaries(point, range.upper);
  return (
    (lower > 0 || (lower === 0 && range.lowerInclusive)) &&
    (upper < 0 || (upper === 0 && range.upperInclusive))
  );
}

function normalizedDominanceRequestRange(
  request: DominanceRequest,
): Record<string, unknown> | null {
  if (request.range === undefined) return null;
  const lower =
    request.range.lower === undefined || request.range.lower === "-oo"
      ? "-oo"
      : canonicalRequestExactScalar(request.range.lower);
  const upper =
    request.range.upper === undefined || request.range.upper === "oo"
      ? "oo"
      : canonicalRequestExactScalar(request.range.upper);
  if (lower === null || upper === null) return null;
  return {
    lower,
    upper,
    lower_inclusive:
      request.range.lower_inclusive ?? (lower === "-oo" ? false : true),
    upper_inclusive:
      request.range.upper_inclusive ?? (upper === "oo" ? false : true),
  };
}

function dominanceDomainBounds(domain: MathematicalDomain): DominanceBounds {
  const lower = dominanceBoundary(
    domain === "positive_integer" ||
      domain === "nonnegative_integer" ||
      domain === "positive_real" ||
      domain === "nonnegative_real"
      ? "0"
      : "-oo",
  )!;
  return {
    lower,
    upper: { kind: "positive_infinity" },
    lowerInclusive:
      domain === "nonnegative_integer" || domain === "nonnegative_real",
    upperInclusive: false,
  };
}
function dominanceCellBounds(
  cell: Record<string, unknown>,
): DominanceBounds | null {
  if (cell.kind === "real_interval") {
    if (
      !exactKeys(cell, [
        "kind",
        "lower",
        "upper",
        "lower_inclusive",
        "upper_inclusive",
        "dominant",
        "blockers",
      ]) ||
      typeof cell.lower !== "string" ||
      typeof cell.upper !== "string" ||
      typeof cell.lower_inclusive !== "boolean" ||
      typeof cell.upper_inclusive !== "boolean"
    )
      return null;
    const bounds = dominanceBounds(
      cell.lower,
      cell.upper,
      cell.lower_inclusive,
      cell.upper_inclusive,
    );
    if (bounds === null) return null;
    return compareDominanceBoundaries(bounds.lower, bounds.upper) < 0
      ? bounds
      : null;
  }
  if (cell.kind === "integer_range") {
    if (
      !exactKeys(cell, ["kind", "lower", "upper", "dominant", "blockers"]) ||
      typeof cell.lower !== "string" ||
      typeof cell.upper !== "string" ||
      ![cell.lower, cell.upper].every(
        (item) =>
          item === "-oo" ||
          item === "oo" ||
          (canonicalExactScalar(item) && !item.includes("/")),
      )
    )
      return null;
    const bounds = dominanceBounds(
      cell.lower,
      cell.upper,
      cell.lower !== "-oo",
      cell.upper !== "oo",
    );
    return bounds !== null &&
      compareDominanceBoundaries(bounds.lower, bounds.upper) <= 0
      ? bounds
      : null;
  }
  if (cell.kind !== "real_point" && cell.kind !== "integer_point") return null;
  if (
    !exactKeys(cell, ["kind", "value", "dominant", "blockers"]) ||
    typeof cell.value !== "string" ||
    !canonicalExactScalar(cell.value) ||
    (cell.kind === "integer_point" && cell.value.includes("/"))
  )
    return null;
  const point = dominanceBoundary(cell.value)!;
  return {
    lower: point,
    upper: point,
    lowerInclusive: true,
    upperInclusive: true,
  };
}

function sameDominanceCellOutcome(
  left: Record<string, unknown>,
  right: Record<string, unknown>,
): boolean {
  return (
    JSON.stringify(left.dominant) === JSON.stringify(right.dominant) &&
    JSON.stringify(left.blockers) === JSON.stringify(right.blockers)
  );
}

function adjacentIntegerBounds(
  left: DominanceBounds,
  right: DominanceBounds,
): boolean {
  if (left.upper.kind !== "finite" || right.lower.kind !== "finite")
    return false;
  return (
    left.upper.denominator === 1n &&
    right.lower.denominator === 1n &&
    right.lower.numerator - left.upper.numerator === 1n
  );
}

function dominanceCellsHaveValidGeometry(
  cells: Record<string, unknown>[],
  bounds: DominanceBounds[],
  effective: DominanceBounds,
  integer: boolean,
): boolean {
  for (let index = 0; index < cells.length; index += 1) {
    const current = bounds[index]!;
    if (!dominanceBoundsWithin(current, effective)) return false;
    if (index === 0) continue;
    const previous = bounds[index - 1]!;
    const order = compareDominanceBoundaries(previous.upper, current.lower);
    if (
      order > 0 ||
      (order === 0 && previous.upperInclusive && current.lowerInclusive)
    )
      return false;
    const coalescable = integer
      ? adjacentIntegerBounds(previous, current)
      : order === 0 && (previous.upperInclusive || current.lowerInclusive);
    if (
      coalescable &&
      sameDominanceCellOutcome(cells[index - 1]!, cells[index]!)
    )
      return false;
  }
  return true;
}

function finiteBoundaryKey(value: DominanceBoundary): string | null {
  return value.kind === "finite"
    ? `${value.numerator}/${value.denominator}`
    : null;
}

function floorDominanceBoundary(value: DominanceBoundary): bigint | null {
  if (value.kind !== "finite") return null;
  return value.numerator >= 0n
    ? value.numerator / value.denominator
    : -((-value.numerator + value.denominator - 1n) / value.denominator);
}

function ceilDominanceBoundary(value: DominanceBoundary): bigint | null {
  if (value.kind !== "finite") return null;
  return value.numerator >= 0n
    ? (value.numerator + value.denominator - 1n) / value.denominator
    : -(-value.numerator / value.denominator);
}

function integerGapIsExcluded(
  lower: bigint,
  upper: bigint,
  exclusions: Set<string>,
): boolean {
  if (lower > upper) return true;
  if (upper - lower + 1n > BigInt(exclusions.size)) return false;
  for (let value = lower; value <= upper; value += 1n)
    if (!exclusions.has(`${value}/1`)) return false;
  return true;
}

function completeDominanceCoverage(
  cells: DominanceBounds[],
  effective: DominanceBounds,
  exclusions: DominanceBoundary[],
  integer: boolean,
): boolean {
  if (cells.length === 0) return false;
  const excluded = new Set(
    exclusions
      .map(finiteBoundaryKey)
      .filter((value): value is string => value !== null),
  );
  if (!integer) {
    const first = cells[0]!;
    const last = cells[cells.length - 1]!;
    if (
      compareDominanceBoundaries(first.lower, effective.lower) !== 0 ||
      compareDominanceBoundaries(last.upper, effective.upper) !== 0
    )
      return false;
    if (
      effective.lowerInclusive &&
      !first.lowerInclusive &&
      !excluded.has(finiteBoundaryKey(effective.lower) ?? "")
    )
      return false;
    if (
      effective.upperInclusive &&
      !last.upperInclusive &&
      !excluded.has(finiteBoundaryKey(effective.upper) ?? "")
    )
      return false;
    for (let index = 1; index < cells.length; index += 1) {
      const previous = cells[index - 1]!;
      const current = cells[index]!;
      if (compareDominanceBoundaries(previous.upper, current.lower) !== 0)
        return false;
      if (
        !previous.upperInclusive &&
        !current.lowerInclusive &&
        !excluded.has(finiteBoundaryKey(previous.upper) ?? "")
      )
        return false;
    }
    return true;
  }
  const first = cells[0]!;
  const last = cells[cells.length - 1]!;
  const effectiveLow =
    effective.lower.kind === "negative_infinity"
      ? null
      : effective.lowerInclusive
        ? ceilDominanceBoundary(effective.lower)
        : floorDominanceBoundary(effective.lower)! + 1n;
  const effectiveHigh =
    effective.upper.kind === "positive_infinity"
      ? null
      : effective.upperInclusive
        ? floorDominanceBoundary(effective.upper)
        : ceilDominanceBoundary(effective.upper)! - 1n;
  if (effectiveLow === null) {
    if (first.lower.kind !== "negative_infinity") return false;
  } else {
    if (first.lower.kind !== "finite" || first.lower.denominator !== 1n)
      return false;
    if (
      !integerGapIsExcluded(effectiveLow, first.lower.numerator - 1n, excluded)
    )
      return false;
  }
  if (effectiveHigh === null) {
    if (last.upper.kind !== "positive_infinity") return false;
  } else {
    if (last.upper.kind !== "finite" || last.upper.denominator !== 1n)
      return false;
    if (
      !integerGapIsExcluded(last.upper.numerator + 1n, effectiveHigh, excluded)
    )
      return false;
  }
  for (let index = 1; index < cells.length; index += 1) {
    const previous = cells[index - 1]!;
    const current = cells[index]!;
    if (
      previous.upper.kind !== "finite" ||
      current.lower.kind !== "finite" ||
      previous.upper.denominator !== 1n ||
      current.lower.denominator !== 1n ||
      !integerGapIsExcluded(
        previous.upper.numerator + 1n,
        current.lower.numerator - 1n,
        excluded,
      )
    )
      return false;
  }
  return true;
}

function dominanceAnalysisRequest(request: DominanceRequest): AnalysisRequest {
  const {
    operation: _operation,
    axis: _axis,
    fixed: _fixed,
    range: _range,
    ...analysis
  } = request;
  return analysis as AnalysisRequest;
}
function validDominanceResult(
  value: unknown,
  request: DominanceRequest,
): boolean {
  const keys = [
    "kind",
    "status",
    "analysis",
    "metric",
    "axis",
    "axis_domain",
    "fixed",
    "requested_range",
    "effective_range",
    "shared_denominator",
    "terms",
    "cells",
    "exclusions",
    "never_dominant",
    "conditions",
    "assumptions_used",
    "blockers",
    "evidence",
    "dominance_status",
  ];
  if (
    !isRecord(value) ||
    !exactKeys(value, keys) ||
    value.kind !== "dominance_analysis" ||
    value.status !== "success" ||
    value.metric !== "aggregate_abstract_work" ||
    value.axis !== request.axis ||
    !validResult(value.analysis, dominanceAnalysisRequest(request)) ||
    !isRecord(value.fixed) ||
    !Object.values(value.fixed).every(
      (x) => typeof x === "string" && canonicalExactScalar(x),
    ) ||
    Object.prototype.hasOwnProperty.call(value.fixed, request.axis) ||
    ![
      "integer",
      "nonnegative_integer",
      "positive_integer",
      "real",
      "positive_real",
      "nonnegative_real",
    ].includes(String(value.axis_domain)) ||
    !isRecord(request.variables) ||
    value.axis_domain !== request.variables[request.axis]?.domain ||
    !(
      value.requested_range === null || dominanceRange(value.requested_range)
    ) ||
    !(
      value.effective_range === null || dominanceRange(value.effective_range)
    ) ||
    !(
      value.shared_denominator === null ||
      typeof value.shared_denominator === "string"
    ) ||
    !Array.isArray(value.terms) ||
    value.terms.length > 16 ||
    !Array.isArray(value.cells) ||
    value.cells.length > 513 ||
    !Array.isArray(value.exclusions) ||
    value.exclusions.length > 256 ||
    !validStringArray(value.never_dominant) ||
    !validStringArray(value.conditions) ||
    !validRelationshipUses(value.assumptions_used) ||
    !validStringArray(value.blockers) ||
    !Array.isArray(value.evidence) ||
    value.evidence.length > 120 ||
    !["complete", "unresolved", "empty"].includes(
      String(value.dominance_status),
    )
  )
    return false;
  const expectedFixed = request.fixed ?? {};
  const resultFixed = value.fixed as Record<string, string>;
  const expectedFixedKeys = Object.keys(expectedFixed).sort();
  if (
    JSON.stringify(Object.keys(resultFixed).sort()) !==
      JSON.stringify(expectedFixedKeys) ||
    expectedFixedKeys.some(
      (name) =>
        canonicalRequestExactScalar(expectedFixed[name]) !== resultFixed[name],
    )
  )
    return false;
  const expectedRequestedRange = normalizedDominanceRequestRange(request);
  if (
    (request.range !== undefined && expectedRequestedRange === null) ||
    !sameDominanceRange(value.requested_range, expectedRequestedRange)
  )
    return false;
  let effectiveBounds: DominanceBounds | null = null;
  if (value.effective_range !== null) {
    effectiveBounds = dominanceRangeBounds(value.effective_range);
    const domain = dominanceDomainBounds(
      value.axis_domain as MathematicalDomain,
    );
    if (!dominanceBoundsWithin(effectiveBounds, domain)) return false;
    if (
      expectedRequestedRange !== null &&
      !dominanceBoundsWithin(
        effectiveBounds,
        dominanceRangeBounds(expectedRequestedRange),
      )
    )
      return false;
  }
  const terms = value.terms;
  if (
    !terms.every(
      (term) =>
        isRecord(term) &&
        exactKeys(term, ["id", "power", "coefficient", "expression"]) &&
        typeof term.id === "string" &&
        nonNegativeInteger(term.power) &&
        term.id === `power:${term.power}` &&
        typeof term.coefficient === "string" &&
        typeof term.expression === "string",
    ) ||
    !terms.every(
      (term, i) =>
        i === 0 ||
        ((terms[i - 1] as Record<string, unknown>).power as number) >
          ((term as Record<string, unknown>).power as number),
    )
  )
    return false;
  const ids = terms.map(
    (term) => (term as Record<string, unknown>).id as string,
  );
  if (
    new Set(ids).size !== ids.length ||
    !value.never_dominant.every((id) => ids.includes(id)) ||
    new Set(value.never_dominant).size !== value.never_dominant.length
  )
    return false;
  const integer = String(value.axis_domain).includes("integer");
  const cells = value.cells.filter(isRecord);
  if (cells.length !== value.cells.length) return false;
  const cellBounds: DominanceBounds[] = [];
  for (const cell of cells) {
    if (
      !validStringArray(cell.dominant) ||
      !validStringArray(cell.blockers) ||
      cell.dominant.some((id) => !ids.includes(id)) ||
      new Set(cell.dominant).size !== cell.dominant.length ||
      JSON.stringify(cell.dominant) !==
        JSON.stringify(
          ids.filter((id) => (cell.dominant as string[]).includes(id)),
        ) ||
      cell.blockers.length > 0 === cell.dominant.length > 0 ||
      (integer && !String(cell.kind).startsWith("integer")) ||
      (!integer && String(cell.kind).startsWith("integer"))
    )
      return false;
    const bounds = dominanceCellBounds(cell);
    if (bounds === null) return false;
    cellBounds.push(bounds);
  }
  if (
    effectiveBounds !== null &&
    !dominanceCellsHaveValidGeometry(
      cells,
      cellBounds,
      effectiveBounds,
      integer,
    )
  )
    return false;
  const exclusionPoints: DominanceBoundary[] = [];
  let previousExclusion: DominanceBoundary | null = null;
  for (const exclusion of value.exclusions) {
    if (
      !isRecord(exclusion) ||
      !exactKeys(exclusion, ["value", "reason"]) ||
      exclusion.reason !== "pole" ||
      typeof exclusion.value !== "string" ||
      !canonicalExactScalar(exclusion.value) ||
      (integer && exclusion.value.includes("/"))
    )
      return false;
    const point = dominanceBoundary(exclusion.value)!;
    if (
      effectiveBounds === null ||
      !dominancePointWithin(point, effectiveBounds) ||
      (previousExclusion !== null &&
        compareDominanceBoundaries(previousExclusion, point) >= 0) ||
      cellBounds.some((bounds) => dominancePointWithin(point, bounds)) ||
      !value.conditions.includes(`${request.axis} != ${exclusion.value}`)
    )
      return false;
    previousExclusion = point;
    exclusionPoints.push(point);
  }
  const expectedPairs: Array<[string, string]> = [];
  for (let left = 0; left < ids.length; left += 1)
    for (let right = left + 1; right < ids.length; right += 1)
      expectedPairs.push([ids[left]!, ids[right]!]);
  const pairs = value.evidence.map((item) =>
    isRecord(item) && Array.isArray(item.pair) ? item.pair : undefined,
  );
  if (
    !value.evidence.every(
      (item) =>
        isRecord(item) &&
        exactKeys(item, ["pair", "difference", "sign", "roots"]) &&
        Array.isArray(item.pair) &&
        item.pair.length === 2 &&
        expectedPairs.some(
          (pair) => JSON.stringify(pair) === JSON.stringify(item.pair),
        ) &&
        typeof item.difference === "string" &&
        (item.sign === -1 ||
          item.sign === 0 ||
          item.sign === 1 ||
          item.sign === null) &&
        Array.isArray(item.roots) &&
        item.roots.every(
          (root) => typeof root === "string" && canonicalExactScalar(root),
        ),
    ) ||
    new Set(pairs.map((pair) => JSON.stringify(pair))).size !== pairs.length
  )
    return false;
  if (value.dominance_status === "empty")
    return (
      value.effective_range === null &&
      value.cells.length === 0 &&
      value.exclusions.length === 0 &&
      value.blockers.length === 0 &&
      value.never_dominant.length === 0
    );
  if (value.effective_range === null) return false;
  if (value.dominance_status === "complete") {
    if (
      value.blockers.length > 0 ||
      cells.some((cell) => (cell.blockers as unknown[]).length > 0)
    )
      return false;
    if (ids.length === 0)
      return (
        value.cells.length === 0 &&
        value.never_dominant.length === 0 &&
        value.shared_denominator !== null &&
        value.evidence.length === 0 &&
        value.conditions.includes("aggregate work is identically zero")
      );
    const active = new Set(cells.flatMap((cell) => cell.dominant as string[]));
    const expectedNeverDominant = ids.filter((id) => !active.has(id));
    return (
      value.shared_denominator !== null &&
      value.cells.length > 0 &&
      effectiveBounds !== null &&
      completeDominanceCoverage(
        cellBounds,
        effectiveBounds,
        exclusionPoints,
        integer,
      ) &&
      JSON.stringify(value.never_dominant) ===
        JSON.stringify(expectedNeverDominant) &&
      JSON.stringify(pairs) === JSON.stringify(expectedPairs)
    );
  }
  const hasBlocker =
    value.blockers.length > 0 ||
    cells.some((cell) => (cell.blockers as unknown[]).length > 0);
  if (!hasBlocker || value.never_dominant.length > 0) return false;
  return ids.length === 0
    ? value.shared_denominator === null &&
        value.cells.length === 0 &&
        value.evidence.length === 0 &&
        value.never_dominant.length === 0
    : value.shared_denominator !== null;
}

type ExactRational = { numerator: bigint; denominator: bigint };

function exactRational(value: unknown): ExactRational | null {
  if (typeof value !== "string") return null;
  const fraction = /^([+-]?\d+)\/([1-9]\d*)$/.exec(value);
  if (fraction !== null) {
    return {
      numerator: BigInt(fraction[1]),
      denominator: BigInt(fraction[2]),
    };
  }
  const decimal =
    /^([+-]?)(?:(\d+)(?:\.(\d*))?|\.(\d+))(?:[eE]([+-]?\d+))?$/.exec(value);
  if (decimal === null) return null;
  const fractionalDigits = decimal[3] ?? decimal[4] ?? "";
  const exponent = Number(decimal[5] ?? "0");
  if (!Number.isSafeInteger(exponent) || Math.abs(exponent) > 4_096) {
    return { numerator: 0n, denominator: 1n };
  }
  const digits = `${decimal[2] ?? "0"}${fractionalDigits}`;
  const sign = decimal[1] === "-" ? -1n : 1n;
  const scale = fractionalDigits.length - exponent;
  const magnitude = BigInt(digits);
  return scale >= 0
    ? {
        numerator: sign * magnitude,
        denominator: 10n ** BigInt(scale),
      }
    : {
        numerator: sign * magnitude * 10n ** BigInt(-scale),
        denominator: 1n,
      };
}

const MAX_EXACT_DIGITS = 1_024;
const MAX_EXACT_BITS = 3_402;
const EXACT_SCALAR = /^-?(0|[1-9][0-9]*)(\/[1-9][0-9]*|\.[0-9]+)?$/;

function canonicalRational(value: unknown): string | null {
  if (
    typeof value === "number" &&
    (!Number.isSafeInteger(value) || Math.abs(value) > Number.MAX_SAFE_INTEGER)
  )
    return null;
  if (typeof value !== "string" && typeof value !== "number") return null;
  const source = String(value);
  if (source.length > MAX_EXACT_DIGITS * 2 + 2 || !EXACT_SCALAR.test(source))
    return null;
  const negative = source.startsWith("-");
  const body = negative ? source.slice(1) : source;
  let numeratorText: string;
  let denominatorText: string;
  if (body.includes("/")) {
    [numeratorText, denominatorText] = body.split("/", 2) as [string, string];
    if (
      numeratorText.length > MAX_EXACT_DIGITS ||
      denominatorText.length > MAX_EXACT_DIGITS
    )
      return null;
  } else if (body.includes(".")) {
    const [whole, fraction] = body.split(".", 2) as [string, string];
    if (whole.length + fraction.length > MAX_EXACT_DIGITS) return null;
    numeratorText = `${whole}${fraction}`;
    denominatorText = `1${"0".repeat(fraction.length)}`;
  } else {
    if (body.length > MAX_EXACT_DIGITS) return null;
    numeratorText = body;
    denominatorText = "1";
  }
  let numerator = BigInt(numeratorText);
  const denominator = BigInt(denominatorText);
  if (negative) numerator = -numerator;
  if (
    (numerator < 0n ? -numerator : numerator).toString(2).length >
      MAX_EXACT_BITS ||
    denominator.toString(2).length > MAX_EXACT_BITS ||
    numerator <= 0n
  )
    return null;
  const divisor = greatestCommonDivisor(numerator, denominator);
  const reducedNumerator = numerator / divisor;
  const reducedDenominator = denominator / divisor;
  return reducedDenominator === 1n
    ? String(reducedNumerator)
    : `${reducedNumerator}/${reducedDenominator}`;
}

function canonicalOptimizationObjective(
  value: unknown,
): OptimizationObjective | null {
  if (value === undefined) return null;
  if (!isRecord(value) || typeof value.kind !== "string") return null;
  if (value.kind === "unit_work_v1")
    return exactKeys(value, ["kind"]) ? { kind: "unit_work_v1" } : null;
  if (
    value.kind !== "weighted_operations_v1" ||
    !exactKeys(value, ["kind", "weights"]) ||
    !isRecord(value.weights) ||
    !exactKeys(value.weights, [
      "additions",
      "subtractions",
      "multiplications",
      "divisions",
      "powers",
    ])
  )
    return null;
  const additions = canonicalRational(value.weights.additions);
  const subtractions = canonicalRational(value.weights.subtractions);
  const multiplications = canonicalRational(value.weights.multiplications);
  const divisions = canonicalRational(value.weights.divisions);
  const powers = canonicalRational(value.weights.powers);
  if (
    additions === null ||
    subtractions === null ||
    multiplications === null ||
    divisions === null ||
    powers === null
  )
    return null;
  return {
    kind: "weighted_operations_v1",
    weights: { additions, subtractions, multiplications, divisions, powers },
  };
}

function validOptimizationObjective(value: unknown): boolean {
  if (!isRecord(value) || typeof value.kind !== "string") return false;
  if (value.kind === "unit_work_v1") return exactKeys(value, ["kind"]);
  if (
    value.kind !== "weighted_operations_v1" ||
    !exactKeys(value, ["kind", "weights"]) ||
    !isRecord(value.weights) ||
    !exactKeys(value.weights, [
      "additions",
      "subtractions",
      "multiplications",
      "divisions",
      "powers",
    ])
  )
    return false;
  return Object.values(value.weights).every(
    (weight) =>
      typeof weight === "string" && canonicalRational(weight) === weight,
  );
}

const OPTIMIZATION_FAMILIES = [
  "repeated_subexpression",
  "repeated_call",
  "reciprocal_reuse",
  "factoring",
  "redundant_operation_removal",
  "iterator_invariant_hoisting",
  "cross_equation_sharing",
  "horner",
  "finite_polynomial_sum_v1",
] as const;

function requestedOptimizationObjective(
  request: OptimizeRequest,
): OptimizationObjective | null {
  return canonicalOptimizationObjective(request.goal.objective);
}

function validOptimizeRequest(request: OptimizeRequest): boolean {
  const goal = request.goal;
  return (
    isRecord(goal) &&
    exactKeys(goal, ["kind", "semantics", "operating_domain", "objective"]) &&
    goal.kind === "preserve_all_outputs_v1" &&
    goal.semantics === "exact_symbolic_v1" &&
    goal.operating_domain === "submitted_domain_v1" &&
    canonicalOptimizationObjective(goal.objective) !== null &&
    isRecord(request.search) &&
    exactKeys(request.search, ["kind"]) &&
    request.search.kind === "bounded_goal_v1" &&
    isRecord(request.proof) &&
    exactKeys(request.proof, ["kind"]) &&
    request.proof.kind === "verifier_backed_v1" &&
    Number.isSafeInteger(request.projection_limit) &&
    request.projection_limit >= 1 &&
    request.projection_limit <= 16 &&
    !("max_plans" in request) &&
    !("objective" in request) &&
    !("enabled_algorithmic_families" in request)
  );
}

function validOptimizationWorkClaims(
  beforeValue: unknown,
  afterValue: unknown,
  savingsValue: unknown,
): boolean {
  const before = exactRational(beforeValue);
  const after = exactRational(afterValue);
  const savings = exactRational(savingsValue);
  if (
    (before !== null && before.numerator <= 0n) ||
    (after !== null && after.numerator < 0n) ||
    (savings !== null && savings.numerator <= 0n)
  )
    return false;
  if (before === null || after === null || savings === null) return true;
  const differenceNumerator =
    before.numerator * after.denominator - after.numerator * before.denominator;
  const differenceDenominator = before.denominator * after.denominator;
  return (
    differenceNumerator > 0n &&
    differenceNumerator * savings.denominator ===
      savings.numerator * differenceDenominator
  );
}

function validOptimizationSuggestion(
  value: unknown,
  request: AnalysisRequest,
): boolean {
  if (
    !isRecord(value) ||
    !exactKeys(value, [
      "kind",
      "tier",
      "transformations",
      "intermediate",
      "conclusion",
      "evidence",
      "conditions",
      "assumptions_used",
      "objective_before",
      "objective_after",
      "objective_savings",
      "ordering",
      "finite_precision_qualification",
    ])
  )
    return false;
  const kinds = [
    "repeated_subexpression",
    "repeated_call",
    "reciprocal_reuse",
    "factoring",
    "redundant_operation_removal",
    "iterator_invariant_hoisting",
    "cross_equation_sharing",
    "horner",
    "finite_polynomial_sum_v1",
  ];
  const tier =
    value.kind === "finite_polynomial_sum_v1"
      ? "exact_algorithmic_v1"
      : "exact_algebraic_v1";
  if (
    !kinds.includes(String(value.kind)) ||
    value.tier !== tier ||
    !Array.isArray(value.transformations) ||
    value.transformations.length < 1 ||
    value.transformations.length > 128
  )
    return false;
  const seen = new Set<string>();
  const transformationOutputInterfaces: Array<Set<string>> = [];
  const validTransformation = (transformation: unknown): boolean => {
    if (
      !isRecord(transformation) ||
      !exactKeys(transformation, [
        "target",
        "occurrences",
        "original",
        "proposed",
      ]) ||
      !isRecord(transformation.target) ||
      !exactKeys(transformation.target, ["kind", "name"])
    )
      return false;
    const target = transformation.target;
    const targetValid = isExpressionRequest(request)
      ? target.kind === "expression" && target.name === null
      : target.kind === "equation" &&
        typeof target.name === "string" &&
        request.equations.some((equation) => equation.name === target.name);
    if (!targetValid) return false;
    const key = `${target.kind}:${target.name ?? ""}`;
    if (seen.has(key)) return false;
    seen.add(key);
    const targetEquation = isExpressionRequest(request)
      ? undefined
      : request.equations.find((equation) => equation.name === target.name);
    const allowedOutputIndices = new Set(
      Object.keys(targetEquation?.domains ?? {}),
    );
    const validOutputIndices = (indices: unknown): indices is string[] =>
      validStringArray(indices) &&
      indices.length <= 32 &&
      indices.every((index) => allowedOutputIndices.has(index));
    transformationOutputInterfaces.push(allowedOutputIndices);
    return (
      Array.isArray(transformation.occurrences) &&
      transformation.occurrences.length >= 1 &&
      transformation.occurrences.length <= 128 &&
      transformation.occurrences.every(
        (occurrence) =>
          isRecord(occurrence) &&
          exactKeys(occurrence, ["path", "binders", "output_indices"]) &&
          Array.isArray(occurrence.path) &&
          occurrence.path.length <= 128 &&
          occurrence.path.every(nonNegativeInteger) &&
          validStringArray(occurrence.binders) &&
          occurrence.binders.length <= 32 &&
          validOutputIndices(occurrence.output_indices),
      ) &&
      validInterpretation(transformation.original) &&
      validInterpretation(transformation.proposed)
    );
  };
  if (
    !value.transformations.every(validTransformation) ||
    (value.kind === "cross_equation_sharing"
      ? value.transformations.length < 2
      : value.transformations.length !== 1)
  )
    return false;
  const requiresIntermediate = [
    "repeated_subexpression",
    "repeated_call",
    "reciprocal_reuse",
    "iterator_invariant_hoisting",
    "cross_equation_sharing",
  ].includes(String(value.kind));
  const intermediate = value.intermediate;
  const validIntermediate =
    intermediate === null
      ? !requiresIntermediate
      : requiresIntermediate &&
        isRecord(intermediate) &&
        exactKeys(intermediate, [
          "name",
          "expression",
          "scope_binders",
          "scope_output_indices",
        ]) &&
        typeof intermediate.name === "string" &&
        /^[A-Za-z][A-Za-z0-9_]*$/.test(intermediate.name) &&
        intermediate.name.length <= 128 &&
        validInterpretation(intermediate.expression) &&
        validStringArray(intermediate.scope_binders) &&
        intermediate.scope_binders.length <= 32 &&
        validStringArray(intermediate.scope_output_indices) &&
        intermediate.scope_output_indices.length <= 32 &&
        transformationOutputInterfaces.some((outputInterface) =>
          (intermediate.scope_output_indices as string[]).every((index) =>
            outputInterface.has(index),
          ),
        );
  return (
    validIntermediate &&
    ["proved", "proved_under_assumptions"].includes(String(value.conclusion)) &&
    isRecord(value.evidence) &&
    exactKeys(value.evidence, ["kind", "statement"]) &&
    value.evidence.kind === "identity" &&
    validBoundedDiagnosticText(value.evidence.statement, 4_096) &&
    validStringArray(value.conditions) &&
    value.conditions.length <= 128 &&
    value.conditions.every((condition) =>
      validBoundedDiagnosticText(condition, 4_096),
    ) &&
    validRelationshipUses(value.assumptions_used) &&
    (value.assumptions_used as unknown[]).length <= 128 &&
    (value.conclusion === "proved_under_assumptions") ===
      (value.conditions.length > 0 ||
        (value.assumptions_used as unknown[]).length > 0) &&
    [
      value.objective_before,
      value.objective_after,
      value.objective_savings,
    ].every((item) => validBoundedDiagnosticText(item, 4_096)) &&
    value.objective_before !== value.objective_after &&
    validOptimizationWorkClaims(
      value.objective_before,
      value.objective_after,
      value.objective_savings,
    ) &&
    isRecord(value.ordering) &&
    exactKeys(value.ordering, ["position", "relation_to_previous"]) &&
    positiveInteger(value.ordering.position) &&
    Number(value.ordering.position) <= 16 &&
    ((Number(value.ordering.position) === 1 &&
      value.ordering.relation_to_previous === null) ||
      (Number(value.ordering.position) > 1 &&
        ["previous_proved_superior", "deterministic_non_superiority"].includes(
          String(value.ordering.relation_to_previous),
        ))) &&
    value.finite_precision_qualification === "exact_symbolic_only"
  );
}
function canonicalJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (isRecord(value))
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`)
      .join(",")}}`;
  return JSON.stringify(value);
}

function sameJson(left: unknown, right: unknown): boolean {
  return canonicalJson(left) === canonicalJson(right);
}

function validCandidateEquation(value: unknown): value is EquationRequest {
  if (
    !isRecord(value) ||
    !exactKeys(value, ["name", "expression", "domains", "constraints"]) ||
    typeof value.name !== "string" ||
    typeof value.expression !== "string" ||
    !isRecord(value.domains) ||
    !Array.isArray(value.constraints)
  )
    return false;
  return (
    Object.values(value.domains).every(
      (domain) =>
        isRecord(domain) &&
        exactKeys(domain, ["lower", "upper"]) &&
        typeof domain.lower === "string" &&
        typeof domain.upper === "string",
    ) &&
    value.constraints.every(
      (constraint) =>
        isRecord(constraint) &&
        exactKeys(constraint, ["name", "target", "relationship"]) &&
        [constraint.name, constraint.target, constraint.relationship].every(
          (item) => typeof item === "string",
        ),
    )
  );
}

function normalizedEquationContext(equation: EquationRequest): object {
  return {
    name: equation.name,
    domains: equation.domains ?? {},
    constraints: equation.constraints ?? [],
  };
}

function validOptimizationCandidate(
  value: unknown,
  request: AnalysisRequest | OptimizeRequest,
): value is OptimizationCandidate {
  if (
    !isRecord(value) ||
    !(typeof value.expression === "string"
      ? exactKeys(value, [
          "expression",
          "variables",
          "functions",
          "primitive_costs",
          "assumptions",
          "definitions",
          "outputs",
        ])
      : exactKeys(value, [
          "equations",
          "variables",
          "functions",
          "primitive_costs",
          "assumptions",
          "definitions",
          "outputs",
        ])) ||
    !(value.equations === undefined || Array.isArray(value.equations)) ||
    !(value.equations ?? []).every(validCandidateEquation) ||
    !isRecord(value.variables) ||
    !Array.isArray(value.functions) ||
    !Array.isArray(value.primitive_costs) ||
    !Array.isArray(value.assumptions) ||
    !Array.isArray(value.definitions) ||
    !validStringArray(value.outputs) ||
    value.outputs.length === 0 ||
    new Set(value.outputs).size !== value.outputs.length ||
    !sameJson(value.variables, request.variables ?? {}) ||
    !sameJson(value.functions, request.functions ?? []) ||
    !sameJson(value.primitive_costs, request.primitive_costs ?? []) ||
    !sameJson(value.assumptions, request.assumptions ?? []) ||
    !sameJson(value.definitions, request.definitions ?? [])
  )
    return false;
  if ("expression" in request) {
    return (
      typeof value.expression === "string" &&
      value.equations === undefined &&
      sameJson(value.outputs, ["expression"])
    );
  }
  if (!Array.isArray(value.equations) || value.equations.length === 0)
    return false;
  const equations = value.equations as EquationRequest[];
  const equationNames = equations.map((equation) => equation.name);
  const expectedOutputs = request.equations.map((equation) => equation.name);
  if (
    new Set(equationNames).size !== equationNames.length ||
    !sameJson(value.outputs, expectedOutputs) ||
    !expectedOutputs.every((name) => equationNames.includes(name))
  )
    return false;
  return request.equations.every((source) => {
    const candidate = equations.find(
      (equation) => equation.name === source.name,
    );
    return (
      candidate !== undefined &&
      sameJson(
        normalizedEquationContext(candidate),
        normalizedEquationContext(source),
      )
    );
  });
}

function analysisRequestForTrace(
  request: AnalysisRequest | OptimizeRequest,
): AnalysisRequest {
  return "operation" in request
    ? ({
        ...request,
        operation: undefined,
        goal: undefined,
        search: undefined,
        proof: undefined,
        projection_limit: undefined,
      } as unknown as AnalysisRequest)
    : request;
}

function candidateAsAnalysisRequest(
  candidate: OptimizationCandidate,
): AnalysisRequest {
  return {
    syntax: "sympy",
    ...(candidate.expression !== undefined
      ? { expression: candidate.expression }
      : { equations: candidate.equations }),
    variables: candidate.variables,
    functions: candidate.functions,
    primitive_costs: candidate.primitive_costs,
    assumptions: candidate.assumptions,
    definitions: candidate.definitions,
  };
}

type SerializedCall = { name: string; arguments: string[] };

/** Split the project-owned restricted SymPy call serialization without parsing math. */
function splitSerializedCall(value: string): SerializedCall | null {
  const opening = value.indexOf("(");
  if (opening <= 0 || value[value.length - 1] !== ")") return null;
  const name = value.slice(0, opening);
  if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(name)) return null;
  const arguments_: string[] = [];
  const delimiters: string[] = [];
  let start = opening + 1;
  for (let index = opening + 1; index < value.length; index += 1) {
    const character = value[index]!;
    if (character === "(" || character === "[" || character === "{") {
      delimiters.push(character);
      continue;
    }
    if (character === ")" || character === "]" || character === "}") {
      const openingDelimiter = delimiters.pop();
      if (openingDelimiter !== undefined) {
        if (!(
          (openingDelimiter === "(" && character === ")") ||
          (openingDelimiter === "[" && character === "]") ||
          (openingDelimiter === "{" && character === "}")
        ))
          return null;
        continue;
      }
      if (character !== ")" || index !== value.length - 1) return null;
      const argument = value.slice(start, index).trim();
      if (argument.length === 0) return null;
      arguments_.push(argument);
      return { name, arguments: arguments_ };
    }
    if (character === "," && delimiters.length === 0) {
      const argument = value.slice(start, index).trim();
      if (argument.length === 0) return null;
      arguments_.push(argument);
      start = index + 1;
    }
  }
  return null;
}

function serializedEquation(value: string): [string, string] | null {
  const call = splitSerializedCall(value);
  return call?.name === "Eq" && call.arguments.length === 2
    ? [call.arguments[0]!, call.arguments[1]!]
    : null;
}

function serializedCallEnd(value: string, start: number): number | null {
  const delimiters: string[] = [];
  for (let index = start + 4; index < value.length; index += 1) {
    const character = value[index]!;
    if (character === "(" || character === "[" || character === "{") {
      delimiters.push(character);
      continue;
    }
    if (character !== ")" && character !== "]" && character !== "}") continue;
    const opening = delimiters.pop();
    if (opening !== undefined) {
      if (!(
        (opening === "(" && character === ")") ||
        (opening === "[" && character === "]") ||
        (opening === "{" && character === "}")
      ))
        return null;
      continue;
    }
    return character === ")" ? index : null;
  }
  return null;
}

function projectDeclaredLet(
  value: string,
  name: string,
  declaredValue: string,
): { value: string; matches: number; malformed: boolean } {
  let cursor = 0;
  let matches = 0;
  let malformed = false;
  let projected = "";
  while (cursor < value.length) {
    const start = value.indexOf("Let(", cursor);
    if (start < 0 || (start > 0 && /[A-Za-z0-9_]/.test(value[start - 1]!))) {
      projected += value.slice(cursor);
      break;
    }
    const end = serializedCallEnd(value, start);
    if (end === null) return { value, matches: 0, malformed: true };
    const callText = value.slice(start, end + 1);
    const call = splitSerializedCall(callText);
    if (call === null) return { value, matches: 0, malformed: true };
    projected += value.slice(cursor, start);
    if (call.arguments.length === 3 && call.arguments[0] === name) {
      if (call.arguments[1] !== declaredValue) malformed = true;
      else {
        projected += call.arguments[2]!;
        matches += 1;
      }
    } else projected += callText;
    cursor = end + 1;
  }
  return { value: projected, matches, malformed };
}

function correlatedState(
  candidateValue: string,
  proposed: string,
  intermediate: unknown,
): boolean {
  if (!isRecord(intermediate)) return candidateValue === proposed;
  const expression = intermediate.expression;
  const indices = intermediate.scope_output_indices;
  if (
    typeof intermediate.name !== "string" ||
    !isRecord(expression) ||
    typeof expression.normalized_sympy !== "string" ||
    !Array.isArray(indices) ||
    !indices.every((index) => typeof index === "string")
  )
    return false;
  const projected = projectDeclaredLet(
    candidateValue,
    intermediate.name,
    expression.normalized_sympy,
  );
  // Target-local evidence refers to an output-scoped producer as name[index],
  // while its lexical Let body uses its locally bound bare name.  This is an
  // exact identifier projection, never a target-match fallback.
  const scopedName = `${intermediate.name}[${indices.join(", ")}]`;
  const projectedValue =
    indices.length === 0
      ? projected.value
      : projected.value.replace(
          new RegExp(
            `(?<![A-Za-z0-9_])${intermediate.name}(?![A-Za-z0-9_\\[])`,
            "g",
          ),
          scopedName,
        );
  return (
    !projected.malformed &&
    projected.matches === 1 &&
    projectedValue === proposed
  );
}

function canonicalSerializedSums(value: string): string | null {
  const compact = value.replace(/\s+/g, "");
  let projected = "";
  let cursor = 0;
  while (cursor < compact.length) {
    const start = compact.indexOf("Sum(", cursor);
    if (start < 0) {
      projected += compact.slice(cursor);
      break;
    }
    projected += compact.slice(cursor, start);
    const end = serializedCallEnd(compact, start);
    if (end === null) return null;
    const call = splitSerializedCall(compact.slice(start, end + 1));
    if (call === null || call.name !== "Sum" || call.arguments.length < 2)
      return null;
    const normalizedArguments: string[] = [];
    for (const argument of call.arguments) {
      const normalized = canonicalSerializedSums(argument);
      if (normalized === null) return null;
      normalizedArguments.push(normalized);
    }
    const nested = splitSerializedCall(normalizedArguments[0]!);
    projected +=
      nested?.name === "Sum" && nested.arguments.length >= 2
        ? `Sum(${[...nested.arguments, ...normalizedArguments.slice(1)].join(",")})`
        : `Sum(${normalizedArguments.join(",")})`;
    cursor = end + 1;
  }
  return projected;
}

function enclosingSerializedParentheses(value: string): string {
  let trimmed = value.trim();
  while (trimmed.startsWith("(") && trimmed.endsWith(")")) {
    const end = serializedCallEnd(`wrap${trimmed}`, 0);
    if (end !== trimmed.length + 3) break;
    trimmed = trimmed.slice(1, -1).trim();
  }
  return trimmed;
}

function splitSerializedTuple(value: string): string[] | null {
  const tuple = splitSerializedCall(`Tuple${value.trim()}`);
  return tuple?.name === "Tuple" ? tuple.arguments : null;
}

type SerializedBinary = {
  operator: "+" | "-" | "*" | "/" | "**";
  left: string;
  right: string;
};

function splitSerializedBinary(value: string): SerializedBinary | null {
  const source = enclosingSerializedParentheses(value);
  const operators: Array<{
    index: number;
    width: number;
    precedence: number;
    operator: SerializedBinary["operator"];
  }> = [];
  const delimiters: string[] = [];
  for (let index = 0; index < source.length; index += 1) {
    const character = source[index]!;
    if (character === "(" || character === "[" || character === "{") {
      delimiters.push(character);
      continue;
    }
    if (character === ")" || character === "]" || character === "}") {
      delimiters.pop();
      continue;
    }
    if (delimiters.length > 0) continue;
    const previous = source[index - 1];
    const unary =
      index === 0 || previous === undefined || "+-*/^(,[".includes(previous);
    if ((character === "+" || character === "-") && !unary)
      operators.push({
        index,
        width: 1,
        precedence: 1,
        operator: character,
      });
    else if (character === "*" && source[index + 1] === "*") {
      operators.push({ index, width: 2, precedence: 3, operator: "**" });
      index += 1;
    } else if ((character === "*" || character === "/") && !unary)
      operators.push({
        index,
        width: 1,
        precedence: 2,
        operator: character,
      });
  }
  if (operators.length === 0) return null;
  const minimum = Math.min(...operators.map((operator) => operator.precedence));
  const matching = operators.filter(
    (operator) => operator.precedence === minimum,
  );
  const selected = minimum === 3 ? matching[0]! : matching.at(-1)!;
  return {
    operator: selected.operator,
    left: source.slice(0, selected.index).trim(),
    right: source.slice(selected.index + selected.width).trim(),
  };
}

function serializedStructuralFingerprint(value: string): string | null {
  const normalized = canonicalSerializedSums(value);
  if (normalized === null) return null;

  const fingerprint = (sourceValue: string): string | null => {
    const source = enclosingSerializedParentheses(sourceValue);
    const binary = splitSerializedBinary(source);
    if (binary !== null) {
      if (binary.operator === "+" || binary.operator === "*") {
        const operands: string[] = [];
        const collect = (operand: string): boolean => {
          const nested = splitSerializedBinary(operand);
          if (nested?.operator === binary.operator)
            return collect(nested.left) && collect(nested.right);
          const item = fingerprint(operand);
          if (item === null) return false;
          operands.push(item);
          return true;
        };
        if (!collect(binary.left) || !collect(binary.right)) return null;
        return `${binary.operator}[${operands.sort().join(",")}]`;
      }
      const left = fingerprint(binary.left);
      const right = fingerprint(binary.right);
      return left === null || right === null
        ? null
        : `${binary.operator}[${left},${right}]`;
    }
    const call = splitSerializedCall(source);
    if (call === null) return `atom:${source}`;
    const arguments_ = call.arguments.map(fingerprint);
    return arguments_.some((argument) => argument === null)
      ? null
      : `call:${call.name}(${arguments_.join(",")})`;
  };

  return fingerprint(normalized);
}

type StructuralChildren = {
  values: string[];
  binderOnChild: Array<string | null>;
};

function serializedStructuralChildren(value: string): StructuralChildren {
  const source = enclosingSerializedParentheses(value);
  const binary = splitSerializedBinary(source);
  if (binary !== null) {
    return {
      values: [binary.left, binary.right],
      binderOnChild: [null, null],
    };
  }
  const call = splitSerializedCall(source);
  if (call === null) return { values: [], binderOnChild: [] };
  if (call.name === "Sum" && call.arguments.length >= 2) {
    const limit = splitSerializedTuple(call.arguments.at(-1)!);
    if (limit === null || limit.length !== 3)
      return {
        values: call.arguments,
        binderOnChild: call.arguments.map(() => null),
      };
    const body =
      call.arguments.length === 2
        ? call.arguments[0]!
        : `Sum(${call.arguments.slice(0, -1).join(",")})`;
    return {
      values: [limit[1]!, limit[2]!, body],
      binderOnChild: [null, null, limit[0]!],
    };
  }
  if (call.name === "Let" && call.arguments.length === 3)
    return {
      values: [call.arguments[1]!, call.arguments[2]!],
      binderOnChild: [null, call.arguments[0]!],
    };
  return {
    values: call.arguments,
    binderOnChild: call.arguments.map(() => null),
  };
}

function serializedOccurrenceAtPath(
  value: string,
  path: number[],
): { node: string; binders: string[]; hasSumAncestor: boolean } | null {
  let node = enclosingSerializedParentheses(value);
  const binders: string[] = [];
  let hasSumAncestor = false;
  for (const position of path) {
    if (splitSerializedCall(node)?.name === "Sum") hasSumAncestor = true;
    const children = serializedStructuralChildren(node);
    if (position >= children.values.length) return null;
    const binder = children.binderOnChild[position];
    if (binder !== null && binder !== undefined) binders.push(binder);
    node = enclosingSerializedParentheses(children.values[position]!);
  }
  return { node, binders, hasSumAncestor };
}

function equationOutputIndices(expression: string): string[] | null {
  const equation = serializedEquation(expression);
  if (equation === null) return null;
  const match = /^([A-Za-z][A-Za-z0-9_]*)\[([^\]]+)\]$/.exec(
    equation[0]!.replace(/\s+/g, ""),
  );
  return match === null
    ? []
    : match[2]!.split(",").filter((index) => index.length > 0);
}

function algorithmicTransformationCorrelates(
  step: Record<string, unknown>,
  parent: AnalysisRequest,
): boolean {
  if (step.kind !== "finite_polynomial_sum_v1") return true;
  const transformations = step.transformations as Array<
    Record<string, unknown>
  >;
  if (transformations.length !== 1 || step.intermediate !== null) return false;
  const transformation = transformations[0]!;
  const target = transformation.target as Record<string, unknown>;
  const original = transformation.original as Record<string, unknown>;
  const occurrences = transformation.occurrences as Array<
    Record<string, unknown>
  >;
  if (occurrences.length !== 1 || typeof original.normalized_sympy !== "string")
    return false;
  let parentTarget: string;
  let expectedOutputIndices: string[];
  if (isExpressionRequest(parent)) {
    parentTarget = parent.expression;
    expectedOutputIndices = [];
  } else {
    const equation = parent.equations.find((item) => item.name === target.name);
    if (equation === undefined) return false;
    const parts = serializedEquation(equation.expression);
    expectedOutputIndices = equationOutputIndices(equation.expression) ?? [];
    if (parts === null) return false;
    parentTarget = parts[1]!;
  }
  const originalTarget = isExpressionRequest(parent)
    ? original.normalized_sympy
    : (serializedEquation(original.normalized_sympy)?.[1] ??
      original.normalized_sympy);
  const parentFingerprint = serializedStructuralFingerprint(parentTarget);
  if (
    parentFingerprint === null ||
    parentFingerprint !== serializedStructuralFingerprint(originalTarget)
  )
    return false;
  const occurrence = occurrences[0]!;
  const path = occurrence.path as number[];
  const structuralOccurrence = serializedOccurrenceAtPath(parentTarget, path);
  return (
    structuralOccurrence !== null &&
    structuralOccurrence.node.startsWith("Sum(") &&
    !structuralOccurrence.hasSumAncestor &&
    sameJson(occurrence.binders, structuralOccurrence.binders) &&
    sameJson(occurrence.output_indices, expectedOutputIndices)
  );
}

function traceStateCorrelates(
  step: Record<string, unknown>,
  parent: AnalysisRequest,
  _parentIsSubmittedRequest: boolean,
): boolean {
  const candidate = step.candidate as OptimizationCandidate;
  const transformations = step.transformations as Array<
    Record<string, unknown>
  >;
  const intermediate = step.intermediate;
  if (!algorithmicTransformationCorrelates(step, parent)) return false;
  if (isExpressionRequest(parent)) {
    const transformation = transformations.find(
      (item) => (item.target as Record<string, unknown>).kind === "expression",
    );
    const proposed = transformation?.proposed as
      Record<string, unknown> | undefined;
    return (
      typeof candidate.expression === "string" &&
      typeof proposed?.normalized_sympy === "string" &&
      candidate.expression !== parent.expression &&
      correlatedState(
        candidate.expression,
        proposed.normalized_sympy,
        intermediate,
      )
    );
  }
  if (candidate.equations === undefined) return false;
  const transformed = new Map(
    transformations
      .filter(
        (item) => (item.target as Record<string, unknown>).kind === "equation",
      )
      .map((item) => [
        String((item.target as Record<string, unknown>).name),
        item,
      ]),
  );
  const children = new Map(
    candidate.equations.map((equation) => [equation.name, equation]),
  );
  for (const source of parent.equations) {
    const child = children.get(source.name);
    if (child === undefined) return false;
    const transformation = transformed.get(source.name);
    if (transformation === undefined) {
      // Adapter candidates materialize absent context defaults, but an
      // untouched caller expression itself is serialized byte-for-byte.
      if (
        child.expression !== source.expression ||
        !sameJson(
          normalizedEquationContext(child),
          normalizedEquationContext(source),
        )
      )
        return false;
      continue;
    }
    const sourceParts = serializedEquation(source.expression);
    const childParts = serializedEquation(child.expression);
    const proposed = transformation.proposed as
      Record<string, unknown> | undefined;
    // A global intermediate is correlated through its producer equation;
    // only lexical scope declares a Let wrapper in a target RHS.
    const lexicalIntermediate =
      isRecord(intermediate) &&
      Array.isArray(intermediate.scope_binders) &&
      intermediate.scope_binders.length > 0
        ? intermediate
        : null;
    if (
      sourceParts === null ||
      childParts === null ||
      sourceParts[0] !== childParts[0] ||
      typeof proposed?.normalized_sympy !== "string" ||
      !correlatedState(
        childParts[1],
        proposed.normalized_sympy,
        lexicalIntermediate,
      )
    )
      return false;
  }
  const added = candidate.equations.filter(
    (equation) =>
      !parent.equations.some((source) => source.name === equation.name),
  );
  if (!isRecord(intermediate)) return added.length === 0;
  if (!Array.isArray(intermediate.scope_binders)) return false;
  if (intermediate.scope_binders.length > 0) return added.length === 0;
  const expression = intermediate.expression;
  if (
    added.length !== 1 ||
    typeof intermediate.name !== "string" ||
    added[0]!.name !== intermediate.name ||
    !isRecord(expression) ||
    typeof expression.normalized_sympy !== "string"
  )
    return false;
  const producer = serializedEquation(added[0]!.expression);
  const indices = intermediate.scope_output_indices;
  if (
    !Array.isArray(indices) ||
    !indices.every((item) => typeof item === "string")
  )
    return false;
  const producerDomains = added[0]!.domains ?? {};
  const producerConstraints = added[0]!.constraints ?? [];
  // Multi-target sharing may choose any transformed target with the declared
  // interface; require one exact current parent context rather than assuming
  // generator traversal selected the first target.
  const interfaceMatches = transformations
    .filter(
      (item) => (item.target as Record<string, unknown>).kind === "equation",
    )
    .map((item) =>
      parent.equations.find(
        (equation) =>
          equation.name === (item.target as Record<string, unknown>).name,
      ),
    )
    .some(
      (target) =>
        target !== undefined &&
        sameJson(
          producerDomains,
          Object.fromEntries(
            indices.map((name) => [name, (target.domains ?? {})[name]]),
          ),
        ) &&
        sameJson(
          producerConstraints,
          (target.constraints ?? []).filter((constraint) =>
            indices.includes(constraint.target),
          ),
        ),
    );
  const producerOutput = `${intermediate.name}${
    indices.length === 0 ? "" : `[${indices.join(", ")}]`
  }`;
  return (
    producer !== null &&
    producer[0] === producerOutput &&
    producer[1] === expression.normalized_sympy &&
    interfaceMatches
  );
}

function validOptimizationTraceStep(
  step: Record<string, unknown>,
  parent: AnalysisRequest,
  parentIsSubmittedRequest: boolean,
): boolean {
  // Validate the local evidence against its concrete preceding state, then
  // correlate state changes structurally without applying the transformation.
  const { candidate: _candidate, identity: _identity, ...suggestion } = step;
  return (
    validOptimizationSuggestion(
      { ...suggestion, ordering: { position: 1, relation_to_previous: null } },
      parent,
    ) &&
    isRecord(step.evidence) &&
    step.evidence.statement ===
      (step.tier === "exact_algorithmic_v1"
        ? "independently checked finite-polynomial Sum antidifference and inclusive boundaries"
        : "checked exact symbolic equivalence for every transformed retained output") &&
    traceStateCorrelates(step, parent, parentIsSubmittedRequest)
  );
}

const OPTIMIZATION_LIMIT_KEYS = [
  "depth_one_inspected_nodes",
  "depth_two_inspected_nodes",
  "whole_request_inspected_nodes",
  "generated_transitions_per_depth",
  "complete_reanalyses_per_depth",
  "expanded_parents_depth_two",
  "retained_states_per_depth",
  "aggregate_transformation_nodes_per_depth",
  "proof_steps_per_depth",
  "proof_nodes_per_depth",
  "work_comparison_nodes_per_depth",
  "whole_request_proof_steps",
  "whole_request_proof_nodes",
  "whole_request_work_comparison_nodes",
  "final_states",
  "final_proof_steps",
  "final_proof_nodes",
  "final_work_comparison_nodes",
];

function validSearchLimits(value: unknown): boolean {
  return (
    isRecord(value) &&
    exactKeys(value, OPTIMIZATION_LIMIT_KEYS) &&
    Object.values(value).every(nonNegativeInteger)
  );
}

function validOptimizationPlan(
  value: unknown,
  request: AnalysisRequest | OptimizeRequest,
): value is OptimizationPlan {
  if ("operation" in request && !validOptimizeRequest(request)) return false;
  const expectedObjective =
    "operation" in request ? requestedOptimizationObjective(request) : null;
  if (
    !isRecord(value) ||
    !exactKeys(value, [
      "identity",
      "objective",
      "claim",
      "candidate",
      "suggestion",
      "trace",
    ]) ||
    typeof value.identity !== "string" ||
    !validOptimizationObjective(value.objective) ||
    (expectedObjective !== null &&
      !sameJson(value.objective, expectedObjective)) ||
    Buffer.byteLength(value.identity, "utf8") > MAX_RESPONSE_BYTES ||
    !validOptimizationCandidate(value.candidate, request)
  )
    return false;
  let identity: unknown;
  try {
    identity = JSON.parse(value.identity);
  } catch {
    return false;
  }
  const identityCandidate: Record<string, unknown> = { ...value.candidate };
  if ("expression" in value.candidate) identityCandidate.equations = [];
  if (
    JSON.stringify(identity) !== value.identity ||
    !isRecord(identity) ||
    identity.syntax !== "sympy" ||
    !sameJson(identity, { syntax: "sympy", ...identityCandidate })
  )
    return false;
  if (
    !Array.isArray(value.trace) ||
    value.trace.length < 1 ||
    value.trace.length > 2
  )
    return false;
  const trace = value.trace as unknown[];
  if (
    !isRecord(value.claim) ||
    !exactKeys(value.claim, [
      "kind",
      "proof_policy",
      "objective",
      "semantics",
      "work_semantics",
      "search_policy",
      "families",
      "monotonic_depth",
      "engine",
      "limits",
    ]) ||
    value.claim.kind !== "strict_improvement" ||
    value.claim.proof_policy !== "verifier_backed_v1" ||
    !sameJson(value.claim.objective, value.objective) ||
    value.claim.semantics !== "exact_symbolic_v1" ||
    value.claim.work_semantics !== "aggregate_abstract_work_v1" ||
    value.claim.search_policy !== "bounded_goal_v1" ||
    !sameJson(value.claim.families, OPTIMIZATION_FAMILIES) ||
    value.claim.monotonic_depth !== 2 ||
    value.claim.engine !== "goal_optimizer_v1" ||
    !validSearchLimits(value.claim.limits)
  )
    return false;
  const finalStep = trace[trace.length - 1];
  if (
    !isRecord(finalStep) ||
    !sameJson(finalStep.candidate, value.candidate) ||
    finalStep.identity !== value.identity
  )
    return false;
  let parent: AnalysisRequest = analysisRequestForTrace(request);
  let previousAfter: string | null = null;
  let localRationalSavings = { numerator: 0n, denominator: 1n };
  let allSavingsRational = true;
  for (const [stepIndex, step] of trace.entries()) {
    if (
      !isRecord(step) ||
      !exactKeys(step, [
        "kind",
        "tier",
        "transformations",
        "intermediate",
        "conclusion",
        "evidence",
        "conditions",
        "assumptions_used",
        "objective_before",
        "objective_after",
        "objective_savings",
        "candidate",
        "identity",
        "finite_precision_qualification",
      ]) ||
      typeof step.identity !== "string" ||
      !validOptimizationCandidate(step.candidate, request)
    )
      return false;
    let stepIdentity: unknown;
    try {
      stepIdentity = JSON.parse(step.identity);
    } catch {
      return false;
    }
    const stepCandidate: Record<string, unknown> = {
      ...(step.candidate as Record<string, unknown>),
    };
    if ("expression" in stepCandidate) stepCandidate.equations = [];
    if (
      JSON.stringify(stepIdentity) !== step.identity ||
      !sameJson(stepIdentity, { syntax: "sympy", ...stepCandidate })
    )
      return false;
    // Trace-local transformations must name targets in their actual parent.
    // Objective totals must form one contiguous original-to-final chain.
    if (
      !validOptimizationTraceStep(step, parent, stepIndex === 0) ||
      (previousAfter !== null && step.objective_before !== previousAfter)
    )
      return false;
    previousAfter = String(step.objective_after);
    const localSavings = exactRational(step.objective_savings);
    if (localSavings === null) {
      allSavingsRational = false;
    } else if (allSavingsRational) {
      localRationalSavings = {
        numerator:
          localRationalSavings.numerator * localSavings.denominator +
          localSavings.numerator * localRationalSavings.denominator,
        denominator:
          localRationalSavings.denominator * localSavings.denominator,
      };
    }
    parent = candidateAsAnalysisRequest(
      step.candidate as OptimizationCandidate,
    );
  }
  const analysisRequest = analysisRequestForTrace(request);
  if (
    !validOptimizationSuggestion(value.suggestion, analysisRequest) ||
    !isRecord(value.suggestion) ||
    !isRecord(value.suggestion.evidence) ||
    value.suggestion.evidence.statement !==
      "checked exact symbolic equivalence from submitted computation to final candidate"
  )
    return false;
  const suggestion = value.suggestion as OptimizationSuggestion;
  const firstStep = trace[0] as Record<string, unknown>;
  const lastStep = trace[trace.length - 1] as Record<string, unknown>;
  if (
    firstStep.objective_before !== suggestion.objective_before ||
    lastStep.objective_after !== suggestion.objective_after ||
    !sameJson(lastStep.kind, suggestion.kind) ||
    !sameJson(lastStep.tier, suggestion.tier) ||
    !sameJson(lastStep.transformations, suggestion.transformations) ||
    !sameJson(lastStep.intermediate, suggestion.intermediate) ||
    !trace.every(
      (step) =>
        isRecord(step) &&
        Array.isArray(step.conditions) &&
        step.conditions.every((condition) =>
          suggestion.conditions.includes(String(condition)),
        ),
    )
  )
    return false;
  const finalSavings = exactRational(suggestion.objective_savings);
  return (
    !allSavingsRational ||
    finalSavings === null ||
    localRationalSavings.numerator * finalSavings.denominator ===
      finalSavings.numerator * localRationalSavings.denominator
  );
}

function validOptimizationPlanPopulation(plans: unknown[]): boolean {
  return plans.every((plan, index) => {
    if (!isRecord(plan) || !isRecord(plan.suggestion)) return false;
    const ordering = plan.suggestion.ordering;
    return (
      isRecord(ordering) &&
      ordering.position === index + 1 &&
      (index === 0
        ? ordering.relation_to_previous === null
        : ordering.relation_to_previous === "previous_proved_superior" ||
          ordering.relation_to_previous === "deterministic_non_superiority")
    );
  });
}

function validResult(
  value: unknown,
  request?: AnalysisRequest,
): value is AnalysisSuccess | AnalysisFailure {
  if (!isRecord(value) || typeof value.status !== "string") return false;
  if (value.status === "success") {
    if (request === undefined) return false;
    const keys = [
      "status",
      "interpretation",
      "operation_counts",
      "abstract_work",
      "direct_work_applicability",
      "direct_work_blockers",
      "scenarios",
      "queries",
    ];
    if ("system" in value) keys.push("system");
    return (
      exactKeys(value, keys) &&
      (isExpressionRequest(request) || "system" in value) &&
      validInterpretation(value.interpretation) &&
      validOperationCounts(value.operation_counts) &&
      (value.abstract_work === null ||
        nonNegativeInteger(value.abstract_work)) &&
      validDirectWorkVariant(
        value.direct_work_applicability,
        value.direct_work_blockers,
        [value.abstract_work],
      ) &&
      (!("system" in value) ||
        (validSystemReport(value.system) &&
          isRecord(value.system) &&
          value.system.direct_work_applicability ===
            value.direct_work_applicability &&
          validSystemCorrelation(request, value.system))) &&
      Array.isArray(value.scenarios) &&
      value.scenarios.every(validScenarioResult) &&
      validScenarioCorrelation(request, value.scenarios) &&
      Array.isArray(value.queries) &&
      value.queries.every(validQueryResult) &&
      validQueryCorrelation(request, value.queries as QueryResult[])
    );
  }
  if (value.status === "failure") {
    const error = value.error;
    if (!exactKeys(value, ["status", "error"]) || !isRecord(error))
      return false;
    const errorKeys = [
      "code",
      "message",
      "location",
      "source",
      "supported_alternative",
    ];
    return (
      exactKeys(error, errorKeys) &&
      [
        "malformed_syntax",
        "unsupported_construct",
        "expression_too_complex",
        "normalization_failed",
        "invalid_system",
      ].includes(String(error.code)) &&
      typeof error.message === "string" &&
      (error.location === null || validSourceLocation(error.location)) &&
      (error.source === null ||
        (isRecord(error.source) &&
          exactKeys(error.source, ["path", "span", "excerpt"]) &&
          validBoundedDiagnosticText(error.source.path, 160) &&
          error.source.path.length > 0 &&
          (error.source.span === null || validSourceSpan(error.source.span)) &&
          (error.source.excerpt === null ||
            validBoundedDiagnosticText(error.source.excerpt, 160)))) &&
      validDiagnosticLocationRelation(error.location, error.source) &&
      (error.supported_alternative === null ||
        validBoundedDiagnosticText(error.supported_alternative, 160))
    );
  }
  return false;
}

function validSearchScope(value: unknown): boolean {
  return (
    isRecord(value) &&
    exactKeys(value, [
      "policy",
      "families",
      "monotonic_depth",
      "engine",
      "limits",
      "completion",
      "qualifications",
    ]) &&
    value.policy === "bounded_goal_v1" &&
    sameJson(value.families, OPTIMIZATION_FAMILIES) &&
    value.monotonic_depth === 2 &&
    value.engine === "goal_optimizer_v1" &&
    validSearchLimits(value.limits) &&
    (value.completion === "complete" || value.completion === "incomplete") &&
    validStringArray(value.qualifications) &&
    value.qualifications.length <= 128 &&
    value.qualifications.every((item) =>
      validBoundedDiagnosticText(item, MAX_DIAGNOSTIC_BYTES),
    ) &&
    (value.completion === "incomplete") === value.qualifications.length > 0
  );
}

const BLOCKER_REQUIRED_INFORMATION = {
  missing_primitive_cost: "declare_primitive_cost",
  unproved_domain_or_cardinality: "declare_domain_or_cardinality",
  evaluator_limit: "reduce_evaluator_complexity",
} as const;

function validOptimizationBlocker(
  value: unknown,
  allowedTargets: ReadonlySet<string>,
): boolean {
  return (
    isRecord(value) &&
    exactKeys(value, ["reason", "required_information", "family", "target"]) &&
    Object.hasOwn(BLOCKER_REQUIRED_INFORMATION, String(value.reason)) &&
    value.required_information ===
      BLOCKER_REQUIRED_INFORMATION[
        value.reason as keyof typeof BLOCKER_REQUIRED_INFORMATION
      ] &&
    OPTIMIZATION_FAMILIES.includes(value.family as never) &&
    boundedQueryText(value.target) &&
    value.target.length <= 160 &&
    allowedTargets.has(value.target)
  );
}

function validOptimizationBlockers(
  values: unknown[],
  request: OptimizeRequest,
): boolean {
  const allowedTargets = new Set(
    request.expression !== undefined
      ? ["expression"]
      : (request.equations ?? []).map((equation) => equation.name),
  );
  const seen = new Set<string>();
  for (const value of values) {
    if (!validOptimizationBlocker(value, allowedTargets) || !isRecord(value))
      return false;
    const key = [
      value.reason,
      value.required_information,
      value.family,
      value.target,
    ].join("\u0000");
    if (seen.has(key)) return false;
    seen.add(key);
  }
  return true;
}

function validOptimizeResult(
  value: unknown,
  request: OptimizeRequest,
): boolean {
  if (!validOptimizeRequest(request) || !isRecord(value)) return false;
  if (value.status === "failure")
    return (
      exactKeys(value, ["status", "error"]) &&
      typeof value.error === "string" &&
      value.error.length > 0 &&
      Buffer.byteLength(value.error, "utf8") <= MAX_DIAGNOSTIC_BYTES
    );
  if (
    value.status !== "success" ||
    !exactKeys(value, [
      "status",
      "projection_limit",
      "classification",
      "selection",
      "search_scope",
      "projection_status",
      "projection_qualifications",
      "blockers",
      "plans",
    ])
  )
    return false;
  if (
    value.projection_limit !== request.projection_limit ||
    !isRecord(value.selection) ||
    !exactKeys(value.selection, ["kind", "projection_limit"]) ||
    value.selection.kind !== "deterministic_ranked_prefix" ||
    value.selection.projection_limit !== request.projection_limit ||
    !validSearchScope(value.search_scope) ||
    !["complete", "truncated"].includes(String(value.projection_status)) ||
    !validStringArray(value.projection_qualifications) ||
    value.projection_qualifications.length > 128 ||
    !value.projection_qualifications.every((item) =>
      validBoundedDiagnosticText(item, MAX_DIAGNOSTIC_BYTES),
    ) ||
    (value.projection_status === "truncated") !==
      value.projection_qualifications.length > 0 ||
    !Array.isArray(value.blockers) ||
    value.blockers.length > 16 ||
    !validOptimizationBlockers(value.blockers, request) ||
    !Array.isArray(value.plans) ||
    value.plans.length > request.projection_limit ||
    !validOptimizationPlanPopulation(value.plans) ||
    !value.plans.every((plan) => validOptimizationPlan(plan, request)) ||
    ![
      "plans_returned",
      "no_applicable_candidate",
      "no_verified_improvement",
    ].includes(String(value.classification))
  )
    return false;
  if (
    !value.plans.every(
      (plan) =>
        isRecord(plan) &&
        isRecord(plan.claim) &&
        isRecord(value.search_scope) &&
        sameJson(plan.claim.limits, value.search_scope.limits),
    )
  )
    return false;
  if (value.classification === "plans_returned")
    return value.plans.length > 0 || value.projection_status === "truncated";
  return value.plans.length === 0;
}

export function validateCorrelatedResult(
  request: FormulaRequest,
  value: unknown,
): value is BridgeResult {
  if ("operation" in request && request.operation === "compare_candidates")
    return isRecord(value) && value.status === "failure"
      ? validResult(value)
      : validComparisonResult(value, request);
  if ("operation" in request && request.operation === "optimize")
    return validOptimizeResult(value, request);
  if ("operation" in request && request.operation === "analyze_dominance")
    return isRecord(value) && value.status === "failure"
      ? validResult(value)
      : validDominanceResult(value, request);
  return validResult(value, request);
}
