import { spawn } from "node:child_process";

export const PROTOCOL_VERSION = 1;
export const MAX_RESPONSE_BYTES = 65_536;

export type AnalysisRequest = { syntax: "sympy"; expression: string };
export type BridgeResult = Record<string, unknown>;
export type BridgeFailureKind =
  "environment" | "process" | "timeout" | "malformed-output" | "protocol";
export class BridgeError extends Error {
  constructor(
    readonly kind: BridgeFailureKind,
    message: string,
  ) {
    super(message);
  }
}

export async function invokeAdapter(
  command: string,
  args: string[],
  request: AnalysisRequest,
  timeoutMs = 10_000,
  signal?: AbortSignal,
): Promise<BridgeResult> {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { stdio: ["pipe", "pipe", "pipe"] });
    let stdout = "";
    const timer = setTimeout(() => {
      child.kill();
      reject(new BridgeError("timeout", "formula adapter timed out"));
    }, timeoutMs);
    const abort = () => {
      child.kill();
      reject(new BridgeError("timeout", "formula adapter cancelled"));
    };
    signal?.addEventListener("abort", abort, { once: true });
    child.on("error", () =>
      reject(new BridgeError("environment", "formula adapter could not start")),
    );
    child.stdout.on("data", (chunk: Buffer) => {
      stdout += chunk.toString();
      if (Buffer.byteLength(stdout) > MAX_RESPONSE_BYTES) child.kill();
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      signal?.removeEventListener("abort", abort);
      if (Buffer.byteLength(stdout) > MAX_RESPONSE_BYTES)
        return reject(
          new BridgeError(
            "malformed-output",
            "formula adapter response exceeds its bound",
          ),
        );
      if (code !== 0)
        return reject(
          new BridgeError("process", "formula adapter exited unsuccessfully"),
        );
      try {
        const envelope: unknown = JSON.parse(stdout);
        if (
          !isEnvelope(envelope) ||
          envelope.version !== PROTOCOL_VERSION ||
          !("result" in envelope) ||
          envelope.result === undefined
        ) {
          return reject(
            new BridgeError(
              "protocol",
              "formula adapter returned an incompatible response",
            ),
          );
        }
        resolve(envelope.result);
      } catch {
        reject(
          new BridgeError(
            "malformed-output",
            "formula adapter returned invalid JSON",
          ),
        );
      }
    });
    child.stdin.end(JSON.stringify({ version: PROTOCOL_VERSION, request }));
  });
}
function isEnvelope(
  value: unknown,
): value is { version: number; result?: BridgeResult } {
  return typeof value === "object" && value !== null && "version" in value;
}
