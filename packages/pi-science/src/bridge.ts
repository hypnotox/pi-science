import { TextDecoder } from "node:util";
import { spawnIsolated, terminateTree } from "./process.js";

export const PROTOCOL_VERSION = 9;
export const MAX_FORMULA_BYTES = 65_536;
export const MAX_ENVELOPE_BYTES = 2_097_152;
export const MAX_RESPONSE_BYTES = 262_400;
const MAX_DIAGNOSTIC_BYTES = 4_096;

export type MathematicalDomain =
  | "integer"
  | "nonnegative_integer"
  | "positive_integer"
  | "real"
  | "positive_real"
  | "nonnegative_real";
export type IndexDomain = { lower: string; upper: string };
export type VariableDeclaration = { domain: MathematicalDomain };
export type DomainConstraint = {
  name: string;
  target: string;
  relationship: string;
};
export type EquationRequest = {
  name: string;
  expression: string;
  domains?: Record<string, IndexDomain>;
  constraints?: DomainConstraint[];
};
export type FunctionDefinition = {
  name: string;
  parameters: string[];
  body: string;
};
export type PrimitiveCost = {
  name: string;
  parameters: string[];
  work: string;
};
export type Assumption = { name: string; relationship: string };
export type DirectedDefinition = { variable: string; expression: string };
export type ExactScenarioScalar = string | number;
export type IntervalBound = {
  lower: ExactScenarioScalar;
  upper: ExactScenarioScalar;
  lower_inclusive?: boolean;
  upper_inclusive?: boolean;
};
export type Scenario = {
  name: string;
  fixed?: Record<string, ExactScenarioScalar>;
  choices?: Record<string, ExactScenarioScalar[]>;
  definitions?: DirectedDefinition[];
  asymptotic?: string[];
  bounds?: Record<string, IntervalBound>;
};
export type EquationTarget = { kind: "equation"; name: string };
export type DerivedTarget = { kind: "derived"; query: string };
export type PropertyCheckRequest =
  | { kind: "sign" }
  | {
      kind: "valid_domain" | "singularities" | "monotonicity";
      variable: string;
    };
type QueryCore =
  | {
      name: string;
      kind: "equivalence";
      comparison: string;
      target?: DerivedTarget;
    }
  | { name: string; kind: "closed_form" }
  | {
      name: string;
      kind: "properties";
      checks: PropertyCheckRequest[];
      target?: DerivedTarget;
    }
  | {
      name: string;
      kind: "limit";
      variable: string;
      point: ExactScenarioScalar;
      direction: "left" | "right" | "both";
      target?: DerivedTarget;
    }
  | {
      name: string;
      kind: "limit";
      variable: string;
      point: "oo" | "-oo";
      target?: DerivedTarget;
    }
  | {
      name: string;
      kind: "asymptotic";
      variable: string;
      point: ExactScenarioScalar;
      direction: "left" | "right" | "both";
      order: number;
      target?: DerivedTarget;
    }
  | {
      name: string;
      kind: "asymptotic";
      variable: string;
      point: "oo" | "-oo";
      order: number;
      target?: DerivedTarget;
    };
export type ExpressionQueryRequest = QueryCore;
export type SystemQueryRequest =
  | {
      name: string;
      kind: "equivalence";
      comparison: string;
      target: EquationTarget | DerivedTarget;
    }
  | { name: string; kind: "closed_form"; target: EquationTarget }
  | {
      name: string;
      kind: "properties";
      checks: PropertyCheckRequest[];
      target: EquationTarget | DerivedTarget;
    }
  | {
      name: string;
      kind: "limit";
      variable: string;
      point: ExactScenarioScalar;
      direction: "left" | "right" | "both";
      target: EquationTarget | DerivedTarget;
    }
  | {
      name: string;
      kind: "limit";
      variable: string;
      point: "oo" | "-oo";
      target: EquationTarget | DerivedTarget;
    }
  | {
      name: string;
      kind: "asymptotic";
      variable: string;
      point: ExactScenarioScalar;
      direction: "left" | "right" | "both";
      order: number;
      target: EquationTarget | DerivedTarget;
    }
  | {
      name: string;
      kind: "asymptotic";
      variable: string;
      point: "oo" | "-oo";
      order: number;
      target: EquationTarget | DerivedTarget;
    };
export type QueryRequest = ExpressionQueryRequest | SystemQueryRequest;

type RequestMetadata<Query extends QueryRequest> = {
  variables?: Record<string, VariableDeclaration>;
  functions?: FunctionDefinition[];
  primitive_costs?: PrimitiveCost[];
  assumptions?: Assumption[];
  definitions?: DirectedDefinition[];
  scenarios?: Scenario[];
  queries?: Query[];
};
export type ExpressionAnalysisRequest =
  RequestMetadata<ExpressionQueryRequest> & {
    syntax: "sympy";
    expression: string;
    equations?: never;
  };
export type SystemAnalysisRequest = RequestMetadata<SystemQueryRequest> & {
  syntax: "sympy";
  equations: EquationRequest[];
  expression?: never;
};
export type AnalysisRequest = ExpressionAnalysisRequest | SystemAnalysisRequest;
export type CandidateComputation =
  | { name: string; expression: string; equations?: never }
  | { name: string; equations: EquationRequest[]; expression?: never };
export type CandidateTarget = { kind: "expression" } | EquationTarget;
export type CandidateOutputMapping = {
  name: string;
  targets: Array<{ candidate: string; target: CandidateTarget }>;
};
export type CandidateComparisonRequest = Omit<
  RequestMetadata<QueryRequest>,
  "scenarios" | "queries"
> & {
  syntax: "sympy";
  operation: "compare_candidates";
  candidates: [CandidateComputation, CandidateComputation];
  outputs: CandidateOutputMapping[];
};
export type FormulaRequest = AnalysisRequest | CandidateComparisonRequest;

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
export type CandidateAnalysisReport = {
  name: string;
  analysis: AnalysisSuccess;
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
export type BridgeResult =
  AnalysisSuccess | CandidateComparisonSuccess | AnalysisFailure;

export function appendResponseChunk(
  retained: Buffer,
  chunk: Buffer,
): { retained: Buffer; overflow: boolean } {
  const remaining = MAX_RESPONSE_BYTES - retained.length;
  if (chunk.length <= remaining)
    return { retained: Buffer.concat([retained, chunk]), overflow: false };
  return {
    retained: Buffer.concat([
      retained,
      chunk.subarray(0, Math.max(remaining, 0)),
    ]),
    overflow: true,
  };
}
export type BridgeFailureKind =
  | "environment"
  | "process"
  | "request"
  | "timeout"
  | "cancelled"
  | "malformed-output"
  | "protocol";
export class BridgeError extends Error {
  constructor(
    readonly kind: BridgeFailureKind,
    message: string,
  ) {
    super(message);
  }
}

export function decodeUtf8Strict(value: Uint8Array): string {
  return new TextDecoder("utf-8", { fatal: true }).decode(value);
}

function requestErrorMessage(envelope: unknown): string | undefined {
  if (
    !isRecord(envelope) ||
    !exactKeys(envelope, ["version", "error"]) ||
    envelope.version !== PROTOCOL_VERSION ||
    !isRecord(envelope.error) ||
    !exactKeys(envelope.error, ["kind", "message"]) ||
    envelope.error.kind !== "request" ||
    typeof envelope.error.message !== "string" ||
    envelope.error.message.length === 0 ||
    Buffer.byteLength(envelope.error.message, "utf8") > MAX_DIAGNOSTIC_BYTES
  )
    return undefined;
  return envelope.error.message;
}

export function parseStrictJson(source: string): unknown {
  const parsed: unknown = JSON.parse(source);
  let offset = 0;
  const whitespace = (): void => {
    while (/\s/.test(source[offset] ?? "")) offset += 1;
  };
  const stringToken = (): string => {
    if (source[offset] !== '"') throw new SyntaxError("expected JSON string");
    const start = offset++;
    while (offset < source.length) {
      const character = source[offset++];
      if (character === '"')
        return JSON.parse(source.slice(start, offset)) as string;
      if (character === "\\") {
        const escape = source[offset++];
        if (escape === "u") {
          const digits = source.slice(offset, offset + 4);
          if (!/^[0-9a-fA-F]{4}$/.test(digits))
            throw new SyntaxError("invalid JSON escape");
          offset += 4;
        } else if (!'"\\/bfnrt'.includes(escape ?? "")) {
          throw new SyntaxError("invalid JSON escape");
        }
      } else if (character === undefined || character.charCodeAt(0) < 0x20) {
        throw new SyntaxError("invalid JSON string");
      }
    }
    throw new SyntaxError("unterminated JSON string");
  };
  const value = (): void => {
    whitespace();
    const character = source[offset];
    if (character === "{") {
      offset += 1;
      whitespace();
      const keys = new Set<string>();
      if (source[offset] === "}") {
        offset += 1;
        return;
      }
      while (true) {
        whitespace();
        const key = stringToken();
        if (keys.has(key)) throw new SyntaxError("duplicate JSON object key");
        keys.add(key);
        whitespace();
        if (source[offset++] !== ":")
          throw new SyntaxError("expected JSON colon");
        value();
        whitespace();
        const delimiter = source[offset++];
        if (delimiter === "}") return;
        if (delimiter !== ",")
          throw new SyntaxError("expected JSON object delimiter");
      }
    }
    if (character === "[") {
      offset += 1;
      whitespace();
      if (source[offset] === "]") {
        offset += 1;
        return;
      }
      while (true) {
        value();
        whitespace();
        const delimiter = source[offset++];
        if (delimiter === "]") return;
        if (delimiter !== ",")
          throw new SyntaxError("expected JSON array delimiter");
      }
    }
    if (character === '"') {
      stringToken();
      return;
    }
    const start = offset;
    while (offset < source.length && !/[\s,\]}]/.test(source[offset] ?? ""))
      offset += 1;
    if (start === offset) throw new SyntaxError("expected JSON value");
    JSON.parse(source.slice(start, offset));
  };
  value();
  whitespace();
  if (offset !== source.length) throw new SyntaxError("trailing JSON data");
  return parsed;
}

function boundedText(value: string): string {
  return Buffer.from(value)
    .subarray(0, MAX_DIAGNOSTIC_BYTES)
    .toString("utf8")
    .replace(/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/g, "?");
}
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function exactKeys(
  value: Record<string, unknown>,
  keys: readonly string[],
): boolean {
  return (
    Object.keys(value).length === keys.length &&
    keys.every((key) => key in value)
  );
}
function nonNegativeInteger(value: unknown): boolean {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}
function positiveInteger(value: unknown): boolean {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 1;
}
function validInterpretation(value: unknown): boolean {
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
function validOperationCounts(value: unknown): boolean {
  return (
    isRecord(value) &&
    exactKeys(value, operationKeys) &&
    Object.values(value).every(nonNegativeInteger)
  );
}
function validSymbolicCounts(value: unknown): boolean {
  return (
    isRecord(value) &&
    exactKeys(value, operationKeys) &&
    Object.values(value).every((item) => typeof item === "string")
  );
}
function validStringArray(value: unknown): value is string[] {
  return (
    Array.isArray(value) && value.every((item) => typeof item === "string")
  );
}
function validDirectWorkVariant(
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
function validStringMap(value: unknown): boolean {
  return (
    isRecord(value) &&
    Object.values(value).every((item) => typeof item === "string")
  );
}
function validRelationshipUses(value: unknown): boolean {
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
function validDomainConstraints(value: unknown): boolean {
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
function validEffectiveDomains(value: unknown): boolean {
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
function validConstraintUses(value: unknown): boolean {
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
function validEquationEffectiveDomains(value: unknown): boolean {
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
function validEquationReport(value: unknown): boolean {
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
function validIntervalResult(value: unknown): boolean {
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
function validScenarioResult(value: unknown): boolean {
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
function validSystemReport(value: unknown): boolean {
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
function validBoundedDiagnosticText(
  value: unknown,
  maximum: number,
): value is string {
  return typeof value === "string" && [...value].length <= maximum;
}
function validSourceLocation(value: unknown): boolean {
  return (
    isRecord(value) &&
    exactKeys(value, ["line", "column"]) &&
    positiveInteger(value.line) &&
    nonNegativeInteger(value.column)
  );
}
function validSourceSpan(value: unknown): boolean {
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
function sameLocation(left: unknown, right: unknown): boolean {
  return (
    validSourceLocation(left) &&
    validSourceLocation(right) &&
    (left as { line: number }).line === (right as { line: number }).line &&
    (left as { column: number }).column === (right as { column: number }).column
  );
}
function validDiagnosticLocationRelation(
  location: unknown,
  source: unknown,
): boolean {
  if (source === null) return true;
  if (!isRecord(source)) return false;
  if (source.span === null) return true;
  return isRecord(source.span) && sameLocation(location, source.span.start);
}
function boundedQueryText(value: unknown): value is string {
  return (
    typeof value === "string" && value.length > 0 && [...value].length <= 4096
  );
}
function ordinaryIdentifier(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.length <= 128 &&
    /^[A-Za-z][A-Za-z0-9_]*$/.test(value) &&
    value !== "oo"
  );
}
function validResolvedTarget(value: unknown): boolean {
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
function validPropertyCheck(value: unknown): boolean {
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
function validDerivedCandidate(value: unknown): boolean {
  return (
    isRecord(value) &&
    exactKeys(value, ["interpretation", "operation_counts"]) &&
    validInterpretation(value.interpretation) &&
    validOperationCounts(value.operation_counts)
  );
}
function validNullableQueryText(value: unknown): boolean {
  return value === null || boundedQueryText(value);
}
function canonicalExactScalar(value: string): boolean {
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
function validQueryEvidence(value: unknown): boolean {
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
function validQueryAnswer(value: unknown): boolean {
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
function validQueryResult(value: unknown): boolean {
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

function formulaSources(request: FormulaRequest): string[] {
  const sources: string[] = [];
  if ("expression" in request && request.expression !== undefined)
    sources.push(request.expression);
  if ("equations" in request && request.equations !== undefined)
    for (const equation of request.equations) {
      sources.push(equation.expression);
      for (const domain of Object.values(equation.domains ?? {}))
        sources.push(domain.lower, domain.upper);
      for (const constraint of equation.constraints ?? [])
        sources.push(constraint.relationship);
    }
  for (const definition of request.functions ?? [])
    sources.push(definition.body);
  for (const cost of request.primitive_costs ?? []) sources.push(cost.work);
  for (const assumption of request.assumptions ?? [])
    sources.push(assumption.relationship);
  for (const definition of request.definitions ?? [])
    sources.push(definition.expression);
  for (const scenario of "scenarios" in request
    ? (request.scenarios ?? [])
    : [])
    for (const definition of scenario.definitions ?? [])
      sources.push(definition.expression);
  for (const candidate of "candidates" in request ? request.candidates : []) {
    if (candidate.expression !== undefined) sources.push(candidate.expression);
    for (const equation of candidate.equations ?? []) {
      sources.push(equation.expression);
      for (const domain of Object.values(equation.domains ?? {}))
        sources.push(domain.lower, domain.upper);
      for (const constraint of equation.constraints ?? [])
        sources.push(constraint.relationship);
    }
  }
  for (const query of "queries" in request ? (request.queries ?? []) : []) {
    if (query.kind === "equivalence") sources.push(query.comparison);
    if (query.kind === "limit" || query.kind === "asymptotic")
      sources.push(String(query.point));
  }
  return sources;
}

export async function invokeAdapter(
  command: string,
  args: string[],
  request: FormulaRequest,
  timeoutMs = 10_000,
  signal?: AbortSignal,
): Promise<BridgeResult> {
  if (
    formulaSources(request).some(
      (source) => Buffer.byteLength(source, "utf8") > MAX_FORMULA_BYTES,
    )
  )
    throw new BridgeError(
      "protocol",
      "formula field exceeds 65,536 UTF-8 bytes",
    );
  const payload = JSON.stringify({ version: PROTOCOL_VERSION, request });
  if (Buffer.byteLength(payload, "utf8") > MAX_ENVELOPE_BYTES)
    throw new BridgeError(
      "protocol",
      "formula adapter request envelope exceeds its byte bound",
    );
  if (signal?.aborted)
    throw new BridgeError(
      "cancelled",
      "formula adapter cancelled before start",
    );
  return new Promise((resolve, reject) => {
    const child = spawnIsolated(command, args, {
      stdio: ["pipe", "pipe", "pipe"],
    });
    let stdout: Buffer<ArrayBufferLike> = Buffer.alloc(0);
    let stderr = "";
    let settled = false;
    let cleaning = false;
    const finish = (error?: BridgeError, result?: BridgeResult): void => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      signal?.removeEventListener("abort", abort);
      error ? reject(error) : resolve(result!);
    };
    const cleanup = (kind: BridgeFailureKind, message: string): void => {
      if (cleaning) return;
      cleaning = true;
      terminateTree(child);
      child.once("close", () =>
        finish(
          new BridgeError(
            kind,
            `${message}${stderr ? `: ${boundedText(stderr)}` : ""}`,
          ),
        ),
      );
    };
    const timer = setTimeout(
      () => cleanup("timeout", "formula adapter timed out"),
      timeoutMs,
    );
    const abort = (): void => cleanup("cancelled", "formula adapter cancelled");
    signal?.addEventListener("abort", abort, { once: true });
    // Abort can arrive after the precheck but before this listener is installed.
    if (signal?.aborted) abort();
    child.on("error", (error) =>
      finish(
        new BridgeError(
          "environment",
          `formula adapter could not start: ${boundedText(error.message)}`,
        ),
      ),
    );
    child.stdout!.on("data", (chunk: Buffer) => {
      if (cleaning) return;
      const appended = appendResponseChunk(stdout, chunk);
      stdout = appended.retained;
      if (appended.overflow)
        cleanup(
          "malformed-output",
          "formula adapter response exceeds its bound",
        );
    });
    child.stderr!.on("data", (chunk: Buffer) => {
      stderr = boundedText(stderr + chunk.toString());
    });
    child.on("close", (code) => {
      if (cleaning || settled) return;
      if (stdout.length > MAX_RESPONSE_BYTES)
        return finish(
          new BridgeError(
            "malformed-output",
            "formula adapter response exceeds its bound",
          ),
        );
      if (code !== 0) {
        if (code === 2) {
          try {
            const message = requestErrorMessage(
              parseStrictJson(decodeUtf8Strict(stdout)),
            );
            if (message !== undefined)
              return finish(new BridgeError("request", message));
          } catch {
            // Only an exact bounded request-error envelope changes process failure.
          }
        }
        return finish(
          new BridgeError(
            "process",
            `formula adapter exited unsuccessfully${stderr ? `: ${boundedText(stderr)}` : ""}`,
          ),
        );
      }
      try {
        const envelope = parseStrictJson(decodeUtf8Strict(stdout));
        if (
          !isRecord(envelope) ||
          !exactKeys(envelope, ["version", "result"]) ||
          envelope.version !== PROTOCOL_VERSION ||
          !("operation" in request
            ? isRecord(envelope.result) && envelope.result.status === "failure"
              ? validResult(envelope.result)
              : validComparisonResult(envelope.result, request)
            : validResult(envelope.result, request))
        )
          return finish(
            new BridgeError(
              "protocol",
              "formula adapter returned an incompatible response",
            ),
          );
        finish(undefined, envelope.result as BridgeResult);
      } catch {
        finish(
          new BridgeError(
            "malformed-output",
            "formula adapter returned invalid JSON",
          ),
        );
      }
    });
    child.stdin!.on("error", (error) => {
      // Cleanup itself closes stdin; a prior terminal path owns that race.
      if (cleaning || settled) return;
      cleanup(
        "process",
        `formula adapter stdin failed: ${boundedText(error.message)}`,
      );
    });
    child.stdin!.end(payload);
  });
}
