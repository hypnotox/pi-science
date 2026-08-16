import { execFile } from "node:child_process";
import { promisify } from "node:util";
const exec = promisify(execFile);

export type Readiness =
  | { ready: true; command: string; args: string[] }
  | { ready: false; diagnosis: string };
export type ProvisionOptions = {
  uv?: string;
  revision: string;
  cacheDir?: string;
  repo: string;
  adapter: string;
};
export async function provision(options: ProvisionOptions): Promise<Readiness> {
  const uv = options.uv ?? "uv";
  const cacheDir =
    options.cacheDir ??
    `${process.env.XDG_CACHE_HOME ?? `${process.env.HOME}/.cache`}/pi-science/uv`;
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
  try {
    await exec(uv, [...args, "--health"], {
      env: { ...process.env, UV_CACHE_DIR: cacheDir },
      timeout: 60_000,
    });
    return { ready: true, command: uv, args };
  } catch (error) {
    const detail =
      error instanceof Error && error.message.includes("ENOENT")
        ? "uv is not installed"
        : "Python formula environment could not be provisioned";
    return {
      ready: false,
      diagnosis: `${detail}; install uv, then restart Pi to retry.`,
    };
  }
}
