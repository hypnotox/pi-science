import { spawnIsolated, terminateTree } from "../process.js";
import {
  MAX_ENVELOPE_BYTES,
  MAX_FORMULA_BYTES,
  MAX_RESPONSE_BYTES,
  PROTOCOL_VERSION,
  appendResponseChunk,
  decodeUtf8Strict,
  exactKeys,
  isRecord,
  parseStrictJson,
} from "./protocol.js";
import type { FormulaRequest } from "./requests.js";
import { formulaSources } from "./requests.js";
import type { BridgeResult } from "./results.js";
import {
  BridgeError,
  type BridgeFailureKind,
  boundedText,
  requestErrorMessage,
} from "./diagnostics.js";
import { validateCorrelatedResult } from "./correlation.js";

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
          !validateCorrelatedResult(request, envelope.result)
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
