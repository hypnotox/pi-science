import { PROTOCOL_VERSION, exactKeys, isRecord } from "./protocol.js";

export const MAX_DIAGNOSTIC_BYTES = 4_096;

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

export function requestErrorMessage(envelope: unknown): string | undefined {
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

export function boundedText(value: string): string {
  return Buffer.from(value)
    .subarray(0, MAX_DIAGNOSTIC_BYTES)
    .toString("utf8")
    .replace(/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/g, "?");
}
