import { TextDecoder } from "node:util";

export const PROTOCOL_VERSION = 16;
export const MAX_FORMULA_BYTES = 65_536;
export const MAX_ENVELOPE_BYTES = 2_097_152;
export const MAX_RESPONSE_BYTES = 524_544;
const MAX_DIAGNOSTIC_BYTES = 4_096;

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

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
export function exactKeys(
  value: Record<string, unknown>,
  keys: readonly string[],
): boolean {
  return (
    Object.keys(value).length === keys.length &&
    keys.every((key) => key in value)
  );
}
export function nonNegativeInteger(value: unknown): boolean {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}
export function positiveInteger(value: unknown): boolean {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 1;
}
