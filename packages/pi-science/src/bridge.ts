import { spawn } from "node:child_process";

export const PROTOCOL_VERSION = 1;
export const MAX_RESPONSE_BYTES = 65_536;
export const MAX_EXPRESSION_BYTES = 65_536;
const MAX_DIAGNOSTIC_BYTES = 4_096;

export type AnalysisRequest = { syntax: "sympy"; expression: string };
export type BridgeResult = Record<string, unknown>;
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
function validResult(value: unknown): value is BridgeResult {
  if (!isRecord(value) || typeof value.status !== "string") return false;
  if (value.status === "success") {
    const interpretation = value.interpretation;
    const counts = value.operation_counts;
    return (
      exactKeys(value, [
        "status",
        "interpretation",
        "operation_counts",
        "abstract_work",
      ]) &&
      isRecord(interpretation) &&
      exactKeys(interpretation, ["normalized_sympy", "normalized_latex"]) &&
      typeof interpretation.normalized_sympy === "string" &&
      typeof interpretation.normalized_latex === "string" &&
      isRecord(counts) &&
      exactKeys(counts, [
        "additions",
        "subtractions",
        "multiplications",
        "divisions",
        "powers",
      ]) &&
      Object.values(counts).every(nonNegativeInteger) &&
      nonNegativeInteger(value.abstract_work)
    );
  }
  if (value.status === "failure") {
    const error = value.error;
    return (
      exactKeys(value, ["status", "error"]) &&
      isRecord(error) &&
      exactKeys(error, ["code", "message", "location"]) &&
      [
        "malformed_syntax",
        "unsupported_construct",
        "expression_too_complex",
        "normalization_failed",
      ].includes(String(error.code)) &&
      typeof error.message === "string" &&
      (error.location === null ||
        (isRecord(error.location) &&
          exactKeys(error.location, ["line", "column"]) &&
          positiveInteger(error.location.line) &&
          nonNegativeInteger(error.location.column)))
    );
  }
  return false;
}

export async function invokeAdapter(
  command: string,
  args: string[],
  request: AnalysisRequest,
  timeoutMs = 10_000,
  signal?: AbortSignal,
): Promise<BridgeResult> {
  if (Buffer.byteLength(request.expression, "utf8") > MAX_EXPRESSION_BYTES)
    throw new BridgeError(
      "protocol",
      "formula expression exceeds 65,536 UTF-8 bytes",
    );
  const payload = JSON.stringify({ version: PROTOCOL_VERSION, request });
  if (signal?.aborted)
    throw new BridgeError(
      "cancelled",
      "formula adapter cancelled before start",
    );
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { stdio: ["pipe", "pipe", "pipe"] });
    let stdout = "";
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
      child.kill("SIGTERM");
      setTimeout(() => child.kill("SIGKILL"), 250).unref();
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
    child.on("error", () =>
      finish(new BridgeError("environment", "formula adapter could not start")),
    );
    child.stdout.on("data", (chunk: Buffer) => {
      stdout += chunk.toString();
      if (Buffer.byteLength(stdout) > MAX_RESPONSE_BYTES)
        cleanup(
          "malformed-output",
          "formula adapter response exceeds its bound",
        );
    });
    child.stderr.on("data", (chunk: Buffer) => {
      stderr = boundedText(stderr + chunk.toString());
    });
    child.on("close", (code) => {
      if (cleaning || settled) return;
      if (Buffer.byteLength(stdout) > MAX_RESPONSE_BYTES)
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
        const envelope: unknown = JSON.parse(stdout);
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
    child.stdin.end(payload);
  });
}
