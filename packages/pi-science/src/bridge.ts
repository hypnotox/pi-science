import { TextDecoder } from "node:util";
import { spawnIsolated, terminateTree } from "./process.js";

export const PROTOCOL_VERSION = 2;
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
export type EquationReport = {
  name: string;
  interpretation: Interpretation;
  operation_counts: OperationCounts;
  aggregate_operation_counts: SymbolicOperationCounts;
  aggregate_work: string;
  dependencies: string[];
  primitive_invocations: Record<string, string>;
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
  aggregate_operation_counts: SymbolicOperationCounts;
  total_work: string;
  dependency_edges: [string, string][];
  reuse: Array<{ producer: string; consumer: string; references: number }>;
  primitive_invocations: Record<string, string>;
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
  abstract_work: number;
  system?: SystemReport;
  scenarios: ScenarioResult[];
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
    location?: { line: number; column: number };
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
function validStringArray(value: unknown): boolean {
  return (
    Array.isArray(value) && value.every((item) => typeof item === "string")
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
      "dependencies",
      "primitive_invocations",
      "unknown_costs",
      "unresolved",
      "relationships_used",
    ]) &&
    typeof value.name === "string" &&
    validInterpretation(value.interpretation) &&
    validOperationCounts(value.operation_counts) &&
    validSymbolicCounts(value.aggregate_operation_counts) &&
    typeof value.aggregate_work === "string" &&
    validStringArray(value.dependencies) &&
    validStringMap(value.primitive_invocations) &&
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
    validSymbolicCounts(value.aggregate_operation_counts) &&
    typeof value.total_work === "string" &&
    validEdges &&
    validReuse &&
    validStringMap(value.primitive_invocations) &&
    validStringArray(value.unknown_costs) &&
    validStringArray(value.unresolved) &&
    validStringArray(value.extraction_opportunities) &&
    validRelationshipUses(value.relationships_used) &&
    validStringArray(value.unused_assumptions)
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
      "scenarios",
    ];
    if ("system" in value) keys.push("system");
    return (
      exactKeys(value, keys) &&
      validInterpretation(value.interpretation) &&
      validOperationCounts(value.operation_counts) &&
      nonNegativeInteger(value.abstract_work) &&
      (!("system" in value) || validSystemReport(value.system)) &&
      Array.isArray(value.scenarios) &&
      value.scenarios.every(validScenarioResult)
    );
  }
  if (value.status === "failure") {
    const error = value.error;
    if (!exactKeys(value, ["status", "error"]) || !isRecord(error))
      return false;
    const errorKeys = ["code", "message"];
    if ("location" in error) errorKeys.push("location");
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
      (!("location" in error) ||
        (isRecord(error.location) &&
          exactKeys(error.location, ["line", "column"]) &&
          positiveInteger(error.location.line) &&
          nonNegativeInteger(error.location.column)))
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
