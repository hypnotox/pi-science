import type {
  Assumption,
  CandidateTarget,
  DerivedTarget,
  DirectedDefinition,
  DomainConstraint,
  EquationRequest,
  FunctionDefinition,
  MathematicalDomain,
  PrimitiveCost,
  VariableDeclaration,
} from "./requests.js";
import {
  exactKeys,
  isRecord,
  nonNegativeInteger,
  positiveInteger,
} from "./protocol.js";

export type Interpretation = {
  normalized_sympy: string;
  normalized_latex: string;
};
export type OperationCounts = {
  additions: number;
  subtractions: number;
  multiplications: number;
  divisions: number;
  powers: number;
};
export type SymbolicOperationCounts = {
  additions: string;
  subtractions: string;
  multiplications: string;
  divisions: string;
  powers: string;
};
export type RelationshipUse = { name: string; relationship: string };
export type SourceLocation = { line: number; column: number };
export type SourceSpan = { start: SourceLocation; end: SourceLocation };
export type SourceReference = {
  path: string;
  span: SourceSpan | null;
  excerpt: string | null;
};
export type DirectWorkApplicability = "finite" | "not_finite";
export type EffectiveIndexDomain = {
  index: string;
  lower: string;
  upper: string;
};
export type ConstraintUse = {
  equation: string;
  name: string;
  target: string;
  relationship: string;
};
export type EquationEffectiveDomains = {
  equation: string;
  domains: EffectiveIndexDomain[];
};
export type EquationReport = {
  name: string;
  interpretation: Interpretation;
  operation_counts: OperationCounts;
  aggregate_operation_counts: SymbolicOperationCounts | null;
  aggregate_work: string | null;
  direct_work_applicability: DirectWorkApplicability;
  direct_work_blockers: string[];
  dependencies: string[];
  primitive_invocations: Record<string, string> | null;
  unknown_costs: string[];
  unresolved: string[];
  relationships_used: RelationshipUse[];
  constraints: DomainConstraint[];
  effective_domains: EffectiveIndexDomain[];
  constraint_uses: ConstraintUse[];
};
export type ScenarioResult = {
  name: string;
  substituted_work: string;
  choice_work: Record<string, string>;
  asymptotic?: string;
  interval?: {
    lower: string;
    upper: string;
    lower_inclusive: boolean;
    upper_inclusive: boolean;
    lower_work: string;
    upper_work: string;
    infimum: string;
    supremum: string;
    infimum_attained: boolean;
    supremum_attained: boolean;
    conservative: boolean;
  };
  substitutions: Record<string, string>;
  relationships_used: RelationshipUse[];
  qualifications: string[];
  unresolved: string[];
  effective_domains: EquationEffectiveDomains[];
  choice_effective_domains: Record<string, EquationEffectiveDomains[]>;
};
export type SystemReport = {
  equations: EquationReport[];
  aggregate_operation_counts: SymbolicOperationCounts | null;
  total_work: string | null;
  direct_work_applicability: DirectWorkApplicability;
  direct_work_blockers: string[];
  dependency_edges: [string, string][];
  reuse: Array<{ producer: string; consumer: string; references: number }>;
  primitive_invocations: Record<string, string> | null;
  unknown_costs: string[];
  unresolved: string[];
  extraction_opportunities: string[];
  relationships_used: RelationshipUse[];
  unused_assumptions: string[];
};
export type OptimizationSuggestion = {
  kind:
    | "repeated_subexpression"
    | "repeated_call"
    | "reciprocal_reuse"
    | "factoring"
    | "redundant_operation_removal"
    | "iterator_invariant_hoisting"
    | "cross_equation_sharing"
    | "horner"
    | "finite_polynomial_sum_v1";
  tier: "exact_algebraic_v1" | "exact_algorithmic_v1";
  transformations: Array<{
    target: { kind: "expression" | "equation"; name: string | null };
    occurrences: Array<{
      path: number[];
      binders: string[];
      output_indices: string[];
    }>;
    original: Interpretation;
    proposed: Interpretation;
  }>;
  intermediate: {
    name: string;
    expression: Interpretation;
    scope_binders: string[];
    scope_output_indices: string[];
  } | null;
  conclusion: "proved" | "proved_under_assumptions";
  evidence: { kind: "identity"; statement: string };
  conditions: string[];
  assumptions_used: RelationshipUse[];
  objective_before: string;
  objective_after: string;
  objective_savings: string;
  ordering: {
    position: number;
    relation_to_previous:
      "previous_proved_superior" | "deterministic_non_superiority" | null;
  };
  finite_precision_qualification: "exact_symbolic_only";
};
export type OptimizationCandidate = {
  variables: Record<string, VariableDeclaration>;
  functions: FunctionDefinition[];
  primitive_costs: PrimitiveCost[];
  assumptions: Assumption[];
  definitions: DirectedDefinition[];
  outputs: string[];
} & (
  | { expression: string; equations?: never }
  | { equations: EquationRequest[]; expression?: never }
);
export type OptimizationObjective =
  | { kind: "unit_work_v1" }
  | {
      kind: "weighted_operations_v1";
      weights: Record<
        | "additions"
        | "subtractions"
        | "multiplications"
        | "divisions"
        | "powers",
        string
      >;
    };
export type OptimizationTraceStep = Omit<OptimizationSuggestion, "ordering"> & {
  candidate: OptimizationCandidate;
  identity: string;
};
export type OptimizationPlan = {
  identity: string;
  objective: OptimizationObjective;
  candidate: OptimizationCandidate;
  suggestion: OptimizationSuggestion;
  trace: OptimizationTraceStep[];
};
export type OptimizationReport = {
  requested_limit: number;
  status: "disabled" | "complete" | "incomplete" | "failed";
  suggestions: OptimizationSuggestion[];
  plans: OptimizationPlan[];
  qualifications: string[];
  projection_status: "complete" | "truncated";
  projection_qualifications: string[];
};

export type AnalysisSuccess = {
  status: "success";
  interpretation: Interpretation;
  operation_counts: OperationCounts;
  abstract_work: number | null;
  direct_work_applicability: DirectWorkApplicability;
  direct_work_blockers: string[];
  system?: SystemReport;
  scenarios: ScenarioResult[];
  queries: QueryResult[];
  optimization: OptimizationReport;
};
export type ResolvedTarget =
  { kind: "expression" } | { kind: "equation"; name: string } | DerivedTarget;
export type PropertyCheck =
  | { kind: "sign" }
  | {
      kind: "valid_domain" | "singularities" | "monotonicity";
      variable: string;
    };
export type DerivedCandidate = {
  interpretation: Interpretation;
  operation_counts: OperationCounts;
};
export type QueryAnswer = {
  check: PropertyCheck | null;
  conclusion:
    | "proved"
    | "proved_under_assumptions"
    | "disproved"
    | "unresolved"
    | "inapplicable";
  conditions: string[];
  assumptions_used: RelationshipUse[];
  relevant_unsupported_assumptions: string[];
  blockers: string[];
  evidence: Record<string, unknown> | null;
  derived_candidates: DerivedCandidate[];
  constraint_uses: ConstraintUse[];
};
export type QueryResult = {
  name: string;
  kind: "equivalence" | "closed_form" | "properties" | "limit" | "asymptotic";
  target: ResolvedTarget;
  normalized_target: Interpretation | null;
  summary: string;
  answers: QueryAnswer[];
};
export type AnalysisFailure = {
  status: "failure";
  error: {
    code:
      | "malformed_syntax"
      | "unsupported_construct"
      | "expression_too_complex"
      | "normalization_failed"
      | "invalid_system";
    message: string;
    location: SourceLocation | null;
    source: SourceReference | null;
    supported_alternative: string | null;
  };
};
export type CandidateAnalysisSuccess = Omit<AnalysisSuccess, "system"> & {
  system: SystemReport | null;
};
export type CandidateAnalysisReport = {
  name: string;
  analysis: CandidateAnalysisSuccess;
  aggregate_work: string | null;
};
export type CandidateComparisonSuccess = {
  kind: "candidate_comparison";
  status: "success";
  candidates: [CandidateAnalysisReport, CandidateAnalysisReport];
  outputs: Array<{
    name: string;
    targets: Array<{ candidate: string; target: CandidateTarget }>;
    interface_status: "compatible" | "incompatible" | "unresolved";
    expanded_interpretations: [Interpretation, Interpretation] | null;
    answer: QueryAnswer;
  }>;
  semantic_status:
    | "proved_equal"
    | "proved_equal_under_assumptions"
    | "disproved"
    | "unresolved";
  work_comparison: {
    metric: "aggregate_abstract_work";
    candidate_names: [string, string];
    candidate_works: [string | null, string | null];
    delta: string | null;
    status:
      | "not_comparable"
      | "equal"
      | "first_lower"
      | "second_lower"
      | "crossover"
      | "unresolved";
    conditions: string[];
    assumptions_used: RelationshipUse[];
    relevant_unsupported_assumptions: string[];
    blockers: string[];
    evidence: Record<string, unknown> | null;
  };
};
export type DominanceTerm = {
  id: string;
  power: number;
  coefficient: string;
  expression: string;
};
export type DominanceCell =
  | {
      kind: "real_interval";
      lower: string;
      upper: string;
      lower_inclusive: boolean;
      upper_inclusive: boolean;
      dominant: string[];
      blockers: string[];
    }
  | {
      kind: "real_point" | "integer_point";
      value: string;
      dominant: string[];
      blockers: string[];
    }
  | {
      kind: "integer_range";
      lower: string;
      upper: string;
      dominant: string[];
      blockers: string[];
    };
export type DominanceSuccess = {
  kind: "dominance_analysis";
  status: "success";
  analysis: AnalysisSuccess;
  metric: "aggregate_abstract_work";
  axis: string;
  axis_domain: MathematicalDomain;
  fixed: Record<string, string>;
  requested_range: {
    lower: string;
    upper: string;
    lower_inclusive: boolean;
    upper_inclusive: boolean;
  } | null;
  effective_range: {
    lower: string;
    upper: string;
    lower_inclusive: boolean;
    upper_inclusive: boolean;
  } | null;
  shared_denominator: string | null;
  terms: DominanceTerm[];
  cells: DominanceCell[];
  exclusions: Array<{ value: string; reason: "pole" }>;
  never_dominant: string[];
  conditions: string[];
  assumptions_used: RelationshipUse[];
  blockers: string[];
  evidence: Array<{
    pair: [string, string];
    difference: string;
    sign: -1 | 0 | 1 | null;
    roots: string[];
  }>;
  dominance_status: "complete" | "unresolved" | "empty";
};
export type OptimizationOperationSuccess = {
  status: "success";
  requested_limit: number;
  search_status: "complete" | "incomplete";
  projection_status: "complete" | "truncated";
  plans: OptimizationPlan[];
  qualifications: string[];
  projection_qualifications: string[];
};
export type OptimizationOperationFailure = { status: "failed"; error: string };
export type OptimizationOperationResult =
  OptimizationOperationSuccess | OptimizationOperationFailure;
export type BridgeResult =
  | OptimizationOperationResult
  | AnalysisSuccess
  | CandidateComparisonSuccess
  | DominanceSuccess
  | AnalysisFailure;

export function validInterpretation(value: unknown): boolean {
  return (
    isRecord(value) &&
    exactKeys(value, ["normalized_sympy", "normalized_latex"]) &&
    typeof value.normalized_sympy === "string" &&
    typeof value.normalized_latex === "string"
  );
}
const operationKeys = [
  "additions",
  "subtractions",
  "multiplications",
  "divisions",
  "powers",
] as const;
export function validOperationCounts(value: unknown): boolean {
  return (
    isRecord(value) &&
    exactKeys(value, operationKeys) &&
    Object.values(value).every(nonNegativeInteger)
  );
}
export function validSymbolicCounts(value: unknown): boolean {
  return (
    isRecord(value) &&
    exactKeys(value, operationKeys) &&
    Object.values(value).every((item) => typeof item === "string")
  );
}
export function validStringArray(value: unknown): value is string[] {
  return (
    Array.isArray(value) && value.every((item) => typeof item === "string")
  );
}
export function validDirectWorkVariant(
  applicability: unknown,
  blockers: unknown,
  nullableValues: unknown[],
): boolean {
  if (!validStringArray(blockers)) return false;
  if (applicability === "finite")
    return (
      blockers.length === 0 && nullableValues.every((item) => item !== null)
    );
  return (
    applicability === "not_finite" &&
    blockers.length > 0 &&
    nullableValues.every((item) => item === null)
  );
}
export function validStringMap(value: unknown): boolean {
  return (
    isRecord(value) &&
    Object.values(value).every((item) => typeof item === "string")
  );
}
export function validRelationshipUses(value: unknown): boolean {
  return (
    Array.isArray(value) &&
    value.every(
      (item) =>
        isRecord(item) &&
        exactKeys(item, ["name", "relationship"]) &&
        typeof item.name === "string" &&
        typeof item.relationship === "string",
    )
  );
}
export function validDomainConstraints(value: unknown): boolean {
  return (
    Array.isArray(value) &&
    value.length <= 32 &&
    value.every(
      (item) =>
        isRecord(item) &&
        exactKeys(item, ["name", "target", "relationship"]) &&
        [item.name, item.target, item.relationship].every(
          (part) => typeof part === "string",
        ),
    )
  );
}
export function validEffectiveDomains(value: unknown): boolean {
  return (
    Array.isArray(value) &&
    value.length <= 32 &&
    value.every(
      (item) =>
        isRecord(item) &&
        exactKeys(item, ["index", "lower", "upper"]) &&
        [item.index, item.lower, item.upper].every(
          (part) => typeof part === "string",
        ),
    )
  );
}
export function validConstraintUses(value: unknown): boolean {
  return (
    Array.isArray(value) &&
    value.every(
      (item) =>
        isRecord(item) &&
        exactKeys(item, ["equation", "name", "target", "relationship"]) &&
        [item.equation, item.name, item.target, item.relationship].every(
          (part) => typeof part === "string",
        ),
    )
  );
}
export function validEquationEffectiveDomains(value: unknown): boolean {
  return (
    Array.isArray(value) &&
    value.every(
      (item) =>
        isRecord(item) &&
        exactKeys(item, ["equation", "domains"]) &&
        typeof item.equation === "string" &&
        validEffectiveDomains(item.domains),
    )
  );
}
export function validEquationReport(value: unknown): boolean {
  return (
    isRecord(value) &&
    exactKeys(value, [
      "name",
      "interpretation",
      "operation_counts",
      "aggregate_operation_counts",
      "aggregate_work",
      "direct_work_applicability",
      "direct_work_blockers",
      "dependencies",
      "primitive_invocations",
      "unknown_costs",
      "unresolved",
      "relationships_used",
      "constraints",
      "effective_domains",
      "constraint_uses",
    ]) &&
    typeof value.name === "string" &&
    validInterpretation(value.interpretation) &&
    validOperationCounts(value.operation_counts) &&
    (value.aggregate_operation_counts === null ||
      validSymbolicCounts(value.aggregate_operation_counts)) &&
    (value.aggregate_work === null ||
      typeof value.aggregate_work === "string") &&
    validDirectWorkVariant(
      value.direct_work_applicability,
      value.direct_work_blockers,
      [
        value.aggregate_operation_counts,
        value.aggregate_work,
        value.primitive_invocations,
      ],
    ) &&
    validStringArray(value.dependencies) &&
    (value.primitive_invocations === null ||
      validStringMap(value.primitive_invocations)) &&
    validStringArray(value.unknown_costs) &&
    validStringArray(value.unresolved) &&
    validRelationshipUses(value.relationships_used) &&
    validDomainConstraints(value.constraints) &&
    new Set(
      (value.constraints as Array<Record<string, unknown>>).map(
        (item) => item.name,
      ),
    ).size === (value.constraints as unknown[]).length &&
    validEffectiveDomains(value.effective_domains) &&
    validConstraintUses(value.constraint_uses) &&
    (value.constraint_uses as unknown[]).length ===
      (value.constraints as unknown[]).length &&
    (value.constraint_uses as Array<Record<string, unknown>>).every(
      (use, index) =>
        use.equation === value.name &&
        use.name ===
          (value.constraints as Array<Record<string, unknown>>)[index]?.name &&
        use.target ===
          (value.constraints as Array<Record<string, unknown>>)[index]
            ?.target &&
        use.relationship ===
          (value.constraints as Array<Record<string, unknown>>)[index]
            ?.relationship,
    )
  );
}
export function validIntervalResult(value: unknown): boolean {
  return (
    isRecord(value) &&
    exactKeys(value, [
      "lower",
      "upper",
      "lower_inclusive",
      "upper_inclusive",
      "lower_work",
      "upper_work",
      "infimum",
      "supremum",
      "infimum_attained",
      "supremum_attained",
      "conservative",
    ]) &&
    typeof value.lower === "string" &&
    typeof value.upper === "string" &&
    canonicalExactScalar(value.lower) &&
    canonicalExactScalar(value.upper) &&
    [value.lower_work, value.upper_work, value.infimum, value.supremum].every(
      (item) => typeof item === "string",
    ) &&
    [
      value.lower_inclusive,
      value.upper_inclusive,
      value.infimum_attained,
      value.supremum_attained,
      value.conservative,
    ].every((item) => typeof item === "boolean")
  );
}
export function validScenarioResult(value: unknown): boolean {
  if (!isRecord(value)) return false;
  const keys = [
    "name",
    "substituted_work",
    "choice_work",
    "substitutions",
    "relationships_used",
    "qualifications",
    "unresolved",
    "effective_domains",
    "choice_effective_domains",
  ];
  if ("asymptotic" in value) keys.push("asymptotic");
  if ("interval" in value) keys.push("interval");
  return (
    exactKeys(value, keys) &&
    typeof value.name === "string" &&
    typeof value.substituted_work === "string" &&
    validStringMap(value.choice_work) &&
    (!("asymptotic" in value) || typeof value.asymptotic === "string") &&
    (!("interval" in value) || validIntervalResult(value.interval)) &&
    validStringMap(value.substitutions) &&
    validRelationshipUses(value.relationships_used) &&
    validStringArray(value.qualifications) &&
    validStringArray(value.unresolved) &&
    validEquationEffectiveDomains(value.effective_domains) &&
    isRecord(value.choice_effective_domains) &&
    Object.values(value.choice_effective_domains).every(
      validEquationEffectiveDomains,
    ) &&
    (Object.keys(value.choice_work as object).length === 0
      ? Object.keys(value.choice_effective_domains as object).length === 0
      : (value.effective_domains as unknown[]).length === 0 &&
        Object.keys(value.choice_work as object).length ===
          Object.keys(value.choice_effective_domains as object).length &&
        Object.keys(value.choice_work as object).every(
          (key) => key in (value.choice_effective_domains as object),
        ))
  );
}
export function validSystemReport(value: unknown): boolean {
  if (
    !isRecord(value) ||
    !exactKeys(value, [
      "equations",
      "aggregate_operation_counts",
      "total_work",
      "direct_work_applicability",
      "direct_work_blockers",
      "dependency_edges",
      "reuse",
      "primitive_invocations",
      "unknown_costs",
      "unresolved",
      "extraction_opportunities",
      "relationships_used",
      "unused_assumptions",
    ])
  )
    return false;
  const validEdges =
    Array.isArray(value.dependency_edges) &&
    value.dependency_edges.every(
      (edge) =>
        Array.isArray(edge) &&
        edge.length === 2 &&
        edge.every((item) => typeof item === "string"),
    );
  const validReuse =
    Array.isArray(value.reuse) &&
    value.reuse.every(
      (item) =>
        isRecord(item) &&
        exactKeys(item, ["producer", "consumer", "references"]) &&
        typeof item.producer === "string" &&
        typeof item.consumer === "string" &&
        positiveInteger(item.references),
    );
  return (
    Array.isArray(value.equations) &&
    value.equations.every(validEquationReport) &&
    (value.direct_work_applicability === "not_finite") ===
      value.equations.some(
        (equation) =>
          isRecord(equation) &&
          equation.direct_work_applicability === "not_finite",
      ) &&
    (value.aggregate_operation_counts === null ||
      validSymbolicCounts(value.aggregate_operation_counts)) &&
    (value.total_work === null || typeof value.total_work === "string") &&
    validDirectWorkVariant(
      value.direct_work_applicability,
      value.direct_work_blockers,
      [
        value.aggregate_operation_counts,
        value.total_work,
        value.primitive_invocations,
      ],
    ) &&
    validEdges &&
    validReuse &&
    (value.primitive_invocations === null ||
      validStringMap(value.primitive_invocations)) &&
    validStringArray(value.unknown_costs) &&
    validStringArray(value.unresolved) &&
    validStringArray(value.extraction_opportunities) &&
    validRelationshipUses(value.relationships_used) &&
    validStringArray(value.unused_assumptions)
  );
}
export function validBoundedDiagnosticText(
  value: unknown,
  maximum: number,
): value is string {
  return typeof value === "string" && [...value].length <= maximum;
}
export function validSourceLocation(value: unknown): boolean {
  return (
    isRecord(value) &&
    exactKeys(value, ["line", "column"]) &&
    positiveInteger(value.line) &&
    nonNegativeInteger(value.column)
  );
}
export function validSourceSpan(value: unknown): boolean {
  if (
    !isRecord(value) ||
    !exactKeys(value, ["start", "end"]) ||
    !validSourceLocation(value.start) ||
    !validSourceLocation(value.end)
  )
    return false;
  const start = value.start as { line: number; column: number };
  const end = value.end as { line: number; column: number };
  return (
    end.line > start.line ||
    (end.line === start.line && end.column >= start.column)
  );
}
export function sameLocation(left: unknown, right: unknown): boolean {
  return (
    validSourceLocation(left) &&
    validSourceLocation(right) &&
    (left as { line: number }).line === (right as { line: number }).line &&
    (left as { column: number }).column === (right as { column: number }).column
  );
}
export function validDiagnosticLocationRelation(
  location: unknown,
  source: unknown,
): boolean {
  if (source === null) return true;
  if (!isRecord(source)) return false;
  if (source.span === null) return true;
  return isRecord(source.span) && sameLocation(location, source.span.start);
}
export function boundedQueryText(value: unknown): value is string {
  return (
    typeof value === "string" && value.length > 0 && [...value].length <= 4096
  );
}
export function ordinaryIdentifier(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.length <= 128 &&
    /^[A-Za-z][A-Za-z0-9_]*$/.test(value) &&
    value !== "oo"
  );
}
export function validResolvedTarget(value: unknown): boolean {
  if (!isRecord(value)) return false;
  if (value.kind === "expression") return exactKeys(value, ["kind"]);
  if (value.kind === "derived")
    return (
      exactKeys(value, ["kind", "query"]) && ordinaryIdentifier(value.query)
    );
  return (
    value.kind === "equation" &&
    exactKeys(value, ["kind", "name"]) &&
    ordinaryIdentifier(value.name)
  );
}
export function validPropertyCheck(value: unknown): boolean {
  if (!isRecord(value)) return false;
  if (value.kind === "sign") return exactKeys(value, ["kind"]);
  return (
    ["valid_domain", "singularities", "monotonicity"].includes(
      String(value.kind),
    ) &&
    exactKeys(value, ["kind", "variable"]) &&
    ordinaryIdentifier(value.variable)
  );
}
export function validDerivedCandidate(value: unknown): boolean {
  return (
    isRecord(value) &&
    exactKeys(value, ["interpretation", "operation_counts"]) &&
    validInterpretation(value.interpretation) &&
    validOperationCounts(value.operation_counts)
  );
}
export function validNullableQueryText(value: unknown): boolean {
  return value === null || boundedQueryText(value);
}
export function canonicalExactScalar(value: string): boolean {
  const match = /^(-?)(0|[1-9][0-9]*)(?:\/([1-9][0-9]*))?$/.exec(value);
  if (
    match === null ||
    value === "-0" ||
    match[2].length > 1024 ||
    (match[3]?.length ?? 0) > 1024
  )
    return false;
  try {
    const numerator = BigInt(`${match[1]}${match[2]}`);
    const denominator = BigInt(match[3] ?? "1");
    if (
      (numerator < 0n ? -numerator : numerator).toString(2).length > 3402 ||
      denominator.toString(2).length > 3402
    )
      return false;
    let left = numerator < 0n ? -numerator : numerator;
    let right = denominator;
    while (right !== 0n) [left, right] = [right, left % right];
    return left === 1n && (denominator !== 1n || !value.includes("/"));
  } catch {
    return false;
  }
}
export function validQueryEvidence(value: unknown): boolean {
  if (!isRecord(value) || typeof value.kind !== "string") return false;
  if (value.kind === "identity")
    return (
      exactKeys(value, ["kind", "statement"]) &&
      boundedQueryText(value.statement)
    );
  if (value.kind === "counterexample")
    return (
      exactKeys(value, [
        "kind",
        "substitutions",
        "target_value",
        "comparison_value",
      ]) &&
      validStringMap(value.substitutions) &&
      Object.keys(value.substitutions as Record<string, string>).length <=
        256 &&
      Object.entries(value.substitutions as Record<string, string>).every(
        ([name, item]) =>
          ordinaryIdentifier(name) && canonicalExactScalar(item),
      ) &&
      typeof value.target_value === "string" &&
      canonicalExactScalar(value.target_value) &&
      typeof value.comparison_value === "string" &&
      canonicalExactScalar(value.comparison_value)
    );
  if (value.kind === "closed_form")
    return (
      exactKeys(value, ["kind", "verification", "statement"]) &&
      ["finite_antidifference", "infinite_partial_sum"].includes(
        String(value.verification),
      ) &&
      boundedQueryText(value.statement)
    );
  if (value.kind === "property")
    return (
      exactKeys(value, ["kind", "value", "intervals"]) &&
      boundedQueryText(value.value) &&
      validStringArray(value.intervals) &&
      value.intervals.length <= 256 &&
      value.intervals.every(boundedQueryText)
    );
  if (value.kind === "limit")
    return (
      exactKeys(value, ["kind", "exists", "value", "left", "right"]) &&
      typeof value.exists === "boolean" &&
      validNullableQueryText(value.value) &&
      validNullableQueryText(value.left) &&
      validNullableQueryText(value.right)
    );
  if (value.kind === "asymptotic") {
    const remainder = value.remainder;
    return (
      exactKeys(value, ["kind", "statement", "remainder"]) &&
      boundedQueryText(value.statement) &&
      (remainder === null ||
        (isRecord(remainder) &&
          exactKeys(remainder, [
            "local_parameter",
            "exponent",
            "normalized_big_o",
          ]) &&
          boundedQueryText(remainder.local_parameter) &&
          Number.isSafeInteger(remainder.exponent) &&
          boundedQueryText(remainder.normalized_big_o)))
    );
  }
  return false;
}
export function validQueryAnswer(value: unknown): boolean {
  if (
    !isRecord(value) ||
    !exactKeys(value, [
      "check",
      "conclusion",
      "conditions",
      "assumptions_used",
      "relevant_unsupported_assumptions",
      "blockers",
      "evidence",
      "derived_candidates",
      "constraint_uses",
    ]) ||
    ![
      "proved",
      "proved_under_assumptions",
      "disproved",
      "unresolved",
      "inapplicable",
    ].includes(String(value.conclusion)) ||
    !(value.check === null || validPropertyCheck(value.check)) ||
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
    !(value.evidence === null || validQueryEvidence(value.evidence)) ||
    !Array.isArray(value.derived_candidates) ||
    value.derived_candidates.length > 32 ||
    !value.derived_candidates.every(validDerivedCandidate) ||
    !validConstraintUses(value.constraint_uses)
  )
    return false;
  return !(
    ["unresolved", "inapplicable"].includes(String(value.conclusion)) &&
    value.derived_candidates.length > 0
  );
}
export function validQueryResult(value: unknown): boolean {
  if (
    !isRecord(value) ||
    !exactKeys(value, [
      "name",
      "kind",
      "target",
      "normalized_target",
      "summary",
      "answers",
    ]) ||
    !ordinaryIdentifier(value.name) ||
    ![
      "equivalence",
      "closed_form",
      "properties",
      "limit",
      "asymptotic",
    ].includes(String(value.kind)) ||
    !validResolvedTarget(value.target) ||
    !boundedQueryText(value.summary) ||
    !Array.isArray(value.answers) ||
    !value.answers.every(validQueryAnswer)
  )
    return false;
  const answers = value.answers as QueryAnswer[];
  const sourcePrefix =
    isRecord(value.target) &&
    value.target.kind === "derived" &&
    typeof value.target.query === "string"
      ? `derived target source ${value.target.query} concluded `
      : undefined;
  const sourceConclusions =
    sourcePrefix === undefined
      ? []
      : answers.map((answer) =>
          answer.blockers
            .filter((blocker) => blocker.startsWith(sourcePrefix))
            .map((blocker) => blocker.slice(sourcePrefix.length)),
        );
  const derivedUnavailable =
    sourcePrefix !== undefined &&
    answers.length > 0 &&
    answers.every((answer) => answer.conclusion === "inapplicable") &&
    sourceConclusions.every((items) => items.length === 1) &&
    new Set(sourceConclusions.map((items) => items[0])).size === 1 &&
    [
      "proved",
      "proved_under_assumptions",
      "disproved",
      "unresolved",
      "inapplicable",
    ].includes(sourceConclusions[0]![0]!);
  if (
    (value.normalized_target === null) !== derivedUnavailable ||
    (!derivedUnavailable && !validInterpretation(value.normalized_target)) ||
    (isRecord(value.target) &&
      value.target.kind === "derived" &&
      !["equivalence", "properties", "limit", "asymptotic"].includes(
        String(value.kind),
      ))
  )
    return false;
  if (value.kind === "properties") {
    const checks = answers.map((answer) => JSON.stringify(answer.check));
    return (
      answers.length > 0 &&
      checks.length === new Set(checks).size &&
      answers.every(
        (answer) =>
          answer.check !== null &&
          (answer.evidence === null || answer.evidence.kind === "property"),
      )
    );
  }
  if (answers.length !== 1 || answers[0]?.check !== null) return false;
  const allowedEvidence: Record<string, string> = {
    equivalence: "identity|counterexample",
    closed_form: "closed_form",
    limit: "limit",
    asymptotic: "asymptotic",
  };
  const evidence = answers[0]?.evidence;
  return (
    evidence === null ||
    new RegExp(`^(${allowedEvidence[String(value.kind)]})$`).test(
      String(evidence.kind),
    )
  );
}
