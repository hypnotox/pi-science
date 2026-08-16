import { execFile } from "node:child_process";
import { homedir } from "node:os";
import { isAbsolute, join } from "node:path";
import { promisify } from "node:util";

const exec = promisify(execFile);
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
  timeoutMs?: number;
};

function bounded(value: unknown): string {
  const raw =
    value instanceof Error
      ? "stderr" in value && typeof value.stderr === "string" && value.stderr
        ? value.stderr
        : value.message
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

function healthy(value: unknown): boolean {
  if (typeof value !== "object" || value === null || Array.isArray(value))
    return false;
  const envelope = value as Record<string, unknown>;
  if (
    Object.keys(envelope).length !== 2 ||
    envelope.version !== 1 ||
    typeof envelope.result !== "object" ||
    envelope.result === null ||
    Array.isArray(envelope.result)
  )
    return false;
  const result = envelope.result as Record<string, unknown>;
  return Object.keys(result).length === 1 && result.status === "healthy";
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

  const uv = options.uv ?? "uv";
  const source = `py-science-formula @ git+${options.repo}@${options.revision}#subdirectory=packages/py-science-formula`;
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
  let health: { stdout: string; stderr: string };
  try {
    health = await exec(uv, [...args, "--health"], {
      env: { ...process.env, UV_CACHE_DIR: cacheDir },
      timeout: options.timeoutMs ?? 60_000,
      maxBuffer: MAX_DIAGNOSTIC_BYTES,
      encoding: "utf8",
    });
  } catch (error) {
    return { ready: false, diagnosis: failure(error) };
  }

  let response: unknown;
  try {
    response = JSON.parse(health.stdout);
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
