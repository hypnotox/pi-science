import { TextDecoder } from "node:util";
import { spawnIsolated, terminateTree } from "./process.js";

export const PROTOCOL_VERSION = 4;
export const MAX_FORMULA_BYTES = 65_536;
export const MAX_ENVELOPE_BYTES = 2_097_152;
export const MAX_RESPONSE_BYTES = 262_400;
const MAX_DIAGNOSTIC_BYTES = 4_096;

export type MathematicalDomain =
  | "integer"
  | "nonnegative_integer"
  | "positive_integer"
  | "real"
  | "positive_real";
export type IndexDomain = { lower: string; upper: string };
export type VariableDeclaration = { domain: MathematicalDomain };
export type EquationRequest = {
  name: string;
  expression: string;
  domains?: Record<string, IndexDomain>;
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
export type IntervalBound = { lower: number; upper: number };
export type Scenario = {
  name: string;
  fixed?: Record<string, number>;
  choices?: Record<string, number[]>;
  definitions?: DirectedDefinition[];
  asymptotic?: string[];
  bounds?: Record<string, IntervalBound>;
};
type RequestMetadata = {
  variables?: Record<string, VariableDeclaration>;
  functions?: FunctionDefinition[];
  primitive_costs?: PrimitiveCost[];
  assumptions?: Assumption[];
  definitions?: DirectedDefinition[];
  scenarios?: Scenario[];
};
export type AnalysisRequest =
  | (RequestMetadata & {
      syntax: "sympy";
      expression: string;
      equations?: never;
    })
  | (RequestMetadata & {
      syntax: "sympy";
      equations: EquationRequest[];
      expression?: never;
    });

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
};
export type ScenarioResult = {
  name: string;
  substituted_work: string;
  choice_work: Record<string, string>;
  asymptotic?: string;
  interval?: { lower_work: string; upper_work: string; conservative: boolean };
  substitutions: Record<string, string>;
  relationships_used: RelationshipUse[];
  qualifications: string[];
  unresolved: string[];
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
  { kind: "expression" } | { kind: "equation"; name: string };
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
};
export type QueryResult = {
  name: string;
  kind: "equivalence" | "closed_form" | "properties" | "limit" | "asymptotic";
  target: ResolvedTarget;
  normalized_target: Interpretation;
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
export type BridgeResult = AnalysisSuccess | AnalysisFailure;

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
    validRelationshipUses(value.relationships_used)
  );
}
function validIntervalResult(value: unknown): boolean {
  return (
    isRecord(value) &&
    exactKeys(value, ["lower_work", "upper_work", "conservative"]) &&
    typeof value.lower_work === "string" &&
    typeof value.upper_work === "string" &&
    typeof value.conservative === "boolean"
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
    validStringArray(value.unresolved)
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
      Object.entries(value.substitutions as Record<string, string>).every(
        ([name, item]) =>
          ordinaryIdentifier(name) && canonicalExactScalar(item),
      ) &&
      boundedQueryText(value.target_value) &&
      boundedQueryText(value.comparison_value)
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
    !validStringArray(value.relevant_unsupported_assumptions) ||
    value.relevant_unsupported_assumptions.length > 128 ||
    !value.relevant_unsupported_assumptions.every(boundedQueryText) ||
    !validStringArray(value.blockers) ||
    value.blockers.length > 128 ||
    !value.blockers.every(boundedQueryText) ||
    !(value.evidence === null || validQueryEvidence(value.evidence)) ||
    !Array.isArray(value.derived_candidates) ||
    value.derived_candidates.length > 32 ||
    !value.derived_candidates.every(validDerivedCandidate)
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
    !validInterpretation(value.normalized_target) ||
    !boundedQueryText(value.summary) ||
    !Array.isArray(value.answers) ||
    !value.answers.every(validQueryAnswer)
  )
    return false;
  const answers = value.answers as QueryAnswer[];
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

function validResult(value: unknown): value is BridgeResult {
  if (!isRecord(value) || typeof value.status !== "string") return false;
  if (value.status === "success") {
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
            value.direct_work_applicability)) &&
      Array.isArray(value.scenarios) &&
      value.scenarios.every(validScenarioResult) &&
      Array.isArray(value.queries) &&
      value.queries.every(validQueryResult)
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

function formulaSources(request: AnalysisRequest): string[] {
  const sources: string[] = [];
  if ("expression" in request && request.expression !== undefined)
    sources.push(request.expression);
  if ("equations" in request && request.equations !== undefined)
    for (const equation of request.equations) {
      sources.push(equation.expression);
      for (const domain of Object.values(equation.domains ?? {}))
        sources.push(domain.lower, domain.upper);
    }
  for (const definition of request.functions ?? [])
    sources.push(definition.body);
  for (const cost of request.primitive_costs ?? []) sources.push(cost.work);
  for (const assumption of request.assumptions ?? [])
    sources.push(assumption.relationship);
  for (const definition of request.definitions ?? [])
    sources.push(definition.expression);
  for (const scenario of request.scenarios ?? [])
    for (const definition of scenario.definitions ?? [])
      sources.push(definition.expression);
  return sources;
}

export async function invokeAdapter(
  command: string,
  args: string[],
  request: AnalysisRequest,
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
      if (code !== 0)
        return finish(
          new BridgeError(
            "process",
            `formula adapter exited unsuccessfully${stderr ? `: ${boundedText(stderr)}` : ""}`,
          ),
        );
      try {
        const envelope = parseStrictJson(decodeUtf8Strict(stdout));
        if (
          !isRecord(envelope) ||
          !exactKeys(envelope, ["version", "result"]) ||
          envelope.version !== PROTOCOL_VERSION ||
          !validResult(envelope.result)
        )
          return finish(
            new BridgeError(
              "protocol",
              "formula adapter returned an incompatible response",
            ),
          );
        finish(undefined, envelope.result);
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
