import { execFileSync } from "node:child_process";
import { chmod, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { afterEach, describe, expect, it } from "vitest";
import { provision, type ProvisionOptions } from "../src/provision.js";

const repositoryRoot = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "../../..",
);
const revision = execFileSync("git", ["rev-parse", "HEAD"], {
  cwd: repositoryRoot,
  encoding: "utf8",
}).trim();
const temporaryDirectories = new Set<string>();

async function temporaryDirectory(prefix: string): Promise<string> {
  const directory = await mkdtemp(join(tmpdir(), prefix));
  temporaryDirectories.add(directory);
  return directory;
}

async function executable(body: string): Promise<string> {
  const directory = await temporaryDirectory("pi-science-uv-");
  const path = join(directory, "uv");
  await writeFile(path, `#!/usr/bin/env node\n${body}`);
  await chmod(path, 0o755);
  return path;
}

async function options(uv: string): Promise<ProvisionOptions> {
  return {
    uv,
    cacheDir: await temporaryDirectory("pi-science-cache-"),
    revision,
    repo: pathToFileURL(repositoryRoot).href,
    adapter: resolve(
      repositoryRoot,
      "packages/pi-science/bridge/formula_adapter.py",
    ),
    checkoutRoot: repositoryRoot,
  };
}

const health = JSON.stringify({ version: 11, result: { status: "healthy" } });
const leakedPids: number[] = [];

const pause = (milliseconds: number) =>
  new Promise<void>((resolve) => setTimeout(resolve, milliseconds));

async function readRecordedPid(pidFile: string): Promise<number> {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    try {
      const pid = Number((await readFile(pidFile, "utf8")).trim());
      if (Number.isSafeInteger(pid) && pid > 0) {
        leakedPids.push(pid);
        return pid;
      }
    } catch {
      // The provisioning process has not recorded its descendant yet.
    }
    await pause(10);
  }
  throw new Error("resistant descendant PID was not recorded");
}

async function expectGone(pid: number): Promise<void> {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    try {
      process.kill(pid, 0);
    } catch (error: unknown) {
      if ((error as NodeJS.ErrnoException).code === "ESRCH") return;
      throw error;
    }
    await pause(10);
  }
  throw new Error(`resistant descendant ${pid} remained alive after cleanup`);
}

afterEach(async () => {
  try {
    for (const pid of leakedPids.splice(0)) {
      try {
        process.kill(pid, "SIGKILL");
      } catch {
        // The operation already cleaned up the descendant.
      }
      await expectGone(pid);
    }
  } finally {
    await Promise.all(
      [...temporaryDirectories].map((directory) =>
        rm(directory, { recursive: true, force: true }),
      ),
    );
    temporaryDirectories.clear();
  }
});

describe("eager provisioning", () => {
  it("uses real uv concurrently against one immutable source and external cache", async () => {
    const wrapper = await executable(`
      const fs=require("fs"),path=require("path"),cp=require("child_process");
      const barrier=path.join(process.env.UV_CACHE_DIR,"test-barrier");
      fs.mkdirSync(barrier,{recursive:true});
      fs.writeFileSync(path.join(barrier,String(process.pid)),"ready");
      const wait=()=>{
        if(fs.readdirSync(barrier).length<2) return setTimeout(wait,10);
        const child=cp.spawnSync(process.env.REAL_UV,process.argv.slice(2),{env:process.env,encoding:"utf8"});
        process.stdout.write(child.stdout||"");process.stderr.write(child.stderr||"");
        process.exit(child.status??1);
      };wait();
    `);
    const shared = await options(wrapper);
    const before = execFileSync("git", ["status", "--porcelain=v1"], {
      cwd: repositoryRoot,
      encoding: "utf8",
    });
    const oldUv = process.env.REAL_UV;
    process.env.REAL_UV = execFileSync("bash", ["-lc", "command -v uv"], {
      encoding: "utf8",
    }).trim();
    try {
      const states = await Promise.all([provision(shared), provision(shared)]);
      expect(states.every((state) => state.ready)).toBe(true);
      expect(states[0]).toEqual(states[1]);
    } finally {
      if (oldUv === undefined) delete process.env.REAL_UV;
      else process.env.REAL_UV = oldUv;
    }
    const after = execFileSync("git", ["status", "--porcelain=v1"], {
      cwd: repositoryRoot,
      encoding: "utf8",
    });
    expect(after).toBe(before);
    expect(shared.cacheDir?.startsWith(repositoryRoot)).toBe(false);
  }, 120_000);

  it("normalizes an SCP-style Git origin for uv", async () => {
    const uv = await executable(
      `process.stdout.write(${JSON.stringify(health)})`,
    );
    const state = await provision({
      ...(await options(uv)),
      repo: "git@github.com:hypnotox/pi-science.git",
    });
    expect(state).toMatchObject({ ready: true });
    if (state.ready)
      expect(state.args).toContain(
        `py-science-formula @ git+ssh://git@github.com/hypnotox/pi-science.git@${revision}#subdirectory=packages/py-science-formula`,
      );
  });

  it("makes synchronized injected failures return identical diagnoses", async () => {
    const uv = await executable(`
      const fs=require("fs"),path=require("path");
      const barrier=path.join(process.env.UV_CACHE_DIR,"failure-barrier");
      fs.mkdirSync(barrier,{recursive:true});fs.writeFileSync(path.join(barrier,String(process.pid)),"ready");
      const wait=()=>fs.readdirSync(barrier).length<2?setTimeout(wait,10):(console.error("package build failed"),process.exit(1));wait();
    `);
    const shared = await options(uv);
    const states = await Promise.all([provision(shared), provision(shared)]);
    expect(states[0]).toEqual(states[1]);
    expect(states[0]).toMatchObject({ ready: false });
    if (!states[0]?.ready)
      expect(states[0].diagnosis).toContain("resolution or build failed");
  });

  it.each([
    ["not-json", "malformed health output"],
    [
      JSON.stringify({ version: 2, result: { status: "healthy" } }),
      "incompatible health protocol",
    ],
    [
      JSON.stringify({ version: 1, result: null }),
      "incompatible health protocol",
    ],
    ["", "malformed health output"],
    [
      '{"version":3,"version":3,"result":{"status":"healthy"}}',
      "malformed health output",
    ],
    [
      '{"version":3,"result":{"status":"healthy","status":"healthy"}}',
      "malformed health output",
    ],
  ])("rejects invalid health response %j", async (output, diagnosis) => {
    const uv = await executable(
      `process.stdout.write(${JSON.stringify(output)})`,
    );
    const state = await provision(await options(uv));
    expect(state).toMatchObject({ ready: false });
    if (!state.ready) expect(state.diagnosis).toContain(diagnosis);
  });

  it("rejects invalid UTF-8 health output", async () => {
    const uv = await executable(
      "process.stdout.write(Buffer.from([0x7b,0xff,0x7d]))",
    );
    const state = await provision(await options(uv));
    expect(state).toMatchObject({
      ready: false,
      diagnosis: expect.stringContaining("malformed health output"),
    });
  });

  it("rejects health output one byte above the diagnostic limit", async () => {
    const output = health.padEnd(4097, " ");
    const uv = await executable(
      `process.stdout.write(${JSON.stringify(output)})`,
    );
    const state = await provision(await options(uv));
    expect(state.ready).toBe(false);
  });

  it("rejects oversized health output", async () => {
    const uv = await executable('process.stdout.write("x".repeat(10000))');
    const state = await provision(await options(uv));
    expect(state.ready).toBe(false);
  });

  it("rejects direct and symlinked cache paths inside the managed checkout", async () => {
    const base = await options("unused");
    const direct = await provision({
      ...base,
      cacheDir: join(repositoryRoot, ".cache"),
    });
    expect(direct).toMatchObject({
      ready: false,
      diagnosis: expect.stringContaining("external"),
    });
    const alias = await temporaryDirectory("pi-science-alias-");
    const { symlink } = await import("node:fs/promises");
    await symlink(repositoryRoot, join(alias, "checkout"));
    const linked = await provision({
      ...base,
      cacheDir: join(alias, "checkout", "cache"),
    });
    expect(linked).toMatchObject({
      ready: false,
      diagnosis: expect.stringContaining("external"),
    });
  });

  it("terminates a provisioning tree and removes its recorded SIGTERM-resistant descendant", async () => {
    const pidFile = join(
      tmpdir(),
      `pi-science-provision-descendant-${process.pid}-${Date.now()}-${Math.random()}`,
    );
    const uv = await executable(
      `const fs=require("fs"),cp=require("child_process");const child=cp.spawn(process.execPath,["-e",\`process.on("SIGTERM",()=>{});setInterval(()=>{},1000)\`],{stdio:"ignore"});fs.writeFileSync(${JSON.stringify(pidFile)},String(child.pid));process.on("SIGTERM",()=>{});setInterval(()=>{},1000)`,
    );
    const promise = provision({ ...(await options(uv)), timeoutMs: 250 });
    const pid = await readRecordedPid(pidFile);
    try {
      await expect(promise).resolves.toMatchObject({
        ready: false,
        diagnosis: expect.stringContaining("timed out"),
      });
      await expectGone(pid);
    } finally {
      await rm(pidFile, { force: true });
    }
  });

  it("fails closed with a bounded cache diagnosis when checkout canonicalization races", async () => {
    const base = await options("unused");
    const vanishedRoot = await temporaryDirectory("pi-science-vanished-");
    await rm(vanishedRoot, { recursive: true });
    const state = await provision({ ...base, checkoutRoot: vanishedRoot });
    expect(state).toMatchObject({
      ready: false,
      diagnosis: expect.stringContaining(
        "cache path could not be canonicalized",
      ),
    });
    if (!state.ready)
      expect(Buffer.byteLength(state.diagnosis)).toBeLessThanOrEqual(4_300);
  });

  it("distinguishes immutable identity, cache, executable, timeout, Git, and build failures", async () => {
    const base = await options("/missing/pi-science-uv");
    await expect(
      provision({ ...base, revision: "HEAD" }),
    ).resolves.toMatchObject({
      ready: false,
      diagnosis: expect.stringContaining("checkout identity"),
    });
    await expect(
      provision({ ...base, cacheDir: "relative" }),
    ).resolves.toMatchObject({
      ready: false,
      diagnosis: expect.stringContaining("absolute external"),
    });
    await expect(provision(base)).resolves.toMatchObject({
      ready: false,
      diagnosis: expect.stringContaining("uv is not installed"),
    });

    const timeout = await executable("setTimeout(()=>{},10000)");
    await expect(
      provision({ ...(await options(timeout)), timeoutMs: 20 }),
    ).resolves.toMatchObject({
      ready: false,
      diagnosis: expect.stringContaining("timed out"),
    });

    const git = await executable(
      'console.error("git network connect failed");process.exit(1)',
    );
    await expect(provision(await options(git))).resolves.toMatchObject({
      ready: false,
      diagnosis: expect.stringContaining("pinned Git source"),
    });

    const build = await executable(
      'console.error("dependency build failed");process.exit(1)',
    );
    await expect(provision(await options(build))).resolves.toMatchObject({
      ready: false,
      diagnosis: expect.stringContaining("resolution or build"),
    });
  });
});
