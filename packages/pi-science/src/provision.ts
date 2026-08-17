import { existsSync } from "node:fs";
import { realpath } from "node:fs/promises";
import { homedir } from "node:os";
import { dirname, isAbsolute, join, resolve, sep } from "node:path";
import {
  decodeUtf8Strict,
  parseStrictJson,
  PROTOCOL_VERSION,
} from "./bridge.js";
import { spawnIsolated, terminateTree } from "./process.js";

const MAX_DIAGNOSTIC_BYTES = 4_096;
const SHA = /^[0-9a-f]{40}$/;

export type Readiness =
  | { ready: true; command: string; args: string[] }
  | { ready: false; diagnosis: string };
export type ProvisionOptions = {
  uv?: string;
  revision: string;
  cacheDir?: string;
  repo: string;
  adapter: string;
  checkoutRoot?: string;
  timeoutMs?: number;
};

type CommandResult = {
  stdout: Buffer;
  stdoutOverflow: boolean;
  stderr: string;
  code: number | null;
};

function bounded(value: unknown): string {
  const record =
    typeof value === "object" && value !== null
      ? (value as Record<string, unknown>)
      : undefined;
  const raw =
    record && typeof record.stderr === "string" && record.stderr
      ? record.stderr
      : value instanceof Error
        ? value.message
        : record && typeof record.message === "string"
          ? record.message
          : String(value);
  return Buffer.from(raw)
    .subarray(0, MAX_DIAGNOSTIC_BYTES)
    .toString("utf8")
    .replace(/[\x00-\x1f\x7f]/g, " ")
    .trim();
}

function failure(error: unknown): string {
  const detail = bounded(error);
  const lower = detail.toLowerCase();
  const record =
    typeof error === "object" && error !== null
      ? (error as Record<string, unknown>)
      : undefined;
  let diagnosis: string;
  if (record?.killed === true || lower.includes("timed out"))
    diagnosis = "environment provisioning timed out";
  else if (record?.code === "ENOENT" || lower.includes("enoent"))
    diagnosis = "uv is not installed or is not executable";
  else if (
    lower.includes("python") &&
    (lower.includes("interpreter") || lower.includes("download"))
  )
    diagnosis = "Python 3.13 could not be provisioned";
  else if (
    lower.includes("build") ||
    lower.includes("resolve") ||
    lower.includes("solver")
  )
    diagnosis = "Python package resolution or build failed";
  else if (
    lower.includes("git") ||
    lower.includes("revision") ||
    lower.includes("network") ||
    lower.includes("connect") ||
    lower.includes("dns")
  )
    diagnosis = "the pinned Git source could not be fetched";
  else diagnosis = "Python formula environment could not be provisioned";
  return `${diagnosis}; correct the prerequisite, then reload or restart Pi.${detail ? ` (${detail})` : ""}`;
}

function repositoryUri(repo: string): string {
  const scp = /^([^/:]+@[^/:]+):(.+)$/.exec(repo);
  return scp ? `ssh://${scp[1]}/${scp[2]}` : repo;
}

function cacheDirectory(explicit?: string): string | undefined {
  if (explicit !== undefined)
    return isAbsolute(explicit) ? explicit : undefined;
  const xdg = process.env.XDG_CACHE_HOME;
  if (xdg) return isAbsolute(xdg) ? join(xdg, "pi-science", "uv") : undefined;
  const home = homedir();
  return home && isAbsolute(home)
    ? join(home, ".cache", "pi-science", "uv")
    : undefined;
}

async function nearestRealPath(path: string): Promise<string> {
  let current = resolve(path);
  while (!existsSync(current)) current = dirname(current);
  return realpath(current);
}

async function cacheIsExternal(
  cacheDir: string,
  checkoutRoot?: string,
): Promise<boolean> {
  if (!checkoutRoot) return true;
  const root = await realpath(checkoutRoot);
  const candidate = await nearestRealPath(cacheDir);
  return candidate !== root && !candidate.startsWith(`${root}${sep}`);
}

function healthy(value: unknown): boolean {
  if (typeof value !== "object" || value === null || Array.isArray(value))
    return false;
  const envelope = value as Record<string, unknown>;
  if (
    Object.keys(envelope).length !== 2 ||
    envelope.version !== PROTOCOL_VERSION ||
    typeof envelope.result !== "object" ||
    envelope.result === null ||
    Array.isArray(envelope.result)
  )
    return false;
  const result = envelope.result as Record<string, unknown>;
  return Object.keys(result).length === 1 && result.status === "healthy";
}

async function runBounded(
  command: string,
  args: string[],
  cacheDir: string,
  timeoutMs: number,
): Promise<CommandResult> {
  return new Promise((resolveResult, reject) => {
    const child = spawnIsolated(command, args, {
      env: { ...process.env, UV_CACHE_DIR: cacheDir },
      stdio: ["ignore", "pipe", "pipe"],
    });
    let stdout = Buffer.alloc(0);
    let stdoutOverflow = false;
    let stderr = "";
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      terminateTree(child);
    }, timeoutMs);
    child.stdout!.on("data", (chunk: Buffer) => {
      const remaining = MAX_DIAGNOSTIC_BYTES + 1 - stdout.length;
      if (chunk.length > remaining) stdoutOverflow = true;
      if (remaining > 0)
        stdout = Buffer.concat([stdout, chunk.subarray(0, remaining)]);
    });
    child.stderr!.on("data", (chunk: Buffer) => {
      stderr = bounded(stderr + chunk.toString());
    });
    child.on("error", (error) => {
      clearTimeout(timer);
      reject(error);
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      if (timedOut)
        return reject({ killed: true, message: "timed out", stderr });
      if (code !== 0) return reject({ code, message: stderr, stderr });
      resolveResult({ stdout, stdoutOverflow, stderr, code });
    });
  });
}

export async function provision(options: ProvisionOptions): Promise<Readiness> {
  if (!SHA.test(options.revision))
    return {
      ready: false,
      diagnosis:
        "Pi checkout identity is unavailable; reinstall Pi from an immutable Git pin, then reload or restart Pi.",
    };
  const cacheDir = cacheDirectory(options.cacheDir);
  if (!cacheDir)
    return {
      ready: false,
      diagnosis:
        "An absolute external user cache path is unavailable; configure XDG_CACHE_HOME, then reload or restart Pi.",
    };
  try {
    if (!(await cacheIsExternal(cacheDir, options.checkoutRoot)))
      return {
        ready: false,
        diagnosis:
          "An absolute external user cache path is unavailable; configure XDG_CACHE_HOME, then reload or restart Pi.",
      };
  } catch (error) {
    return {
      ready: false,
      diagnosis: `The cache path could not be canonicalized; configure an accessible absolute external user cache path, then reload or restart Pi.${bounded(error) ? ` (${bounded(error)})` : ""}`,
    };
  }
  const uv = options.uv ?? "uv";
  const source = `py-science-formula @ git+${repositoryUri(options.repo)}@${options.revision}#subdirectory=packages/py-science-formula`;
  const args = [
    "run",
    "--isolated",
    "--no-project",
    "--python",
    "3.13",
    "--with",
    source,
    "python",
    options.adapter,
  ];
  let health: CommandResult;
  try {
    health = await runBounded(
      uv,
      [...args, "--health"],
      cacheDir,
      options.timeoutMs ?? 60_000,
    );
  } catch (error) {
    return { ready: false, diagnosis: failure(error) };
  }
  let response: unknown;
  try {
    if (health.stdoutOverflow) throw new SyntaxError("oversized health output");
    response = parseStrictJson(decodeUtf8Strict(health.stdout));
  } catch {
    return {
      ready: false,
      diagnosis:
        "The formula environment returned malformed health output; reload or reinstall the pinned package.",
    };
  }
  if (!healthy(response))
    return {
      ready: false,
      diagnosis:
        "The formula environment returned an incompatible health protocol; reload or reinstall the pinned package.",
    };
  return { ready: true, command: uv, args };
}
