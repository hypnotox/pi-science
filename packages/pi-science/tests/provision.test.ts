import { chmod, mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { provision } from "../src/provision.js";

async function fakeUv(body: string): Promise<string> {
  const directory = await mkdtemp(join(tmpdir(), "pi-science-uv-"));
  const executable = join(directory, "uv");
  await writeFile(executable, `#!/usr/bin/env node\n${body}`);
  await chmod(executable, 0o755);
  return executable;
}

describe("eager provisioning", () => {
  it("barrier-controls two contending backend processes to one healthy readiness result", async () => {
    const uv = await fakeUv(`
      const fs = require("fs"); const path = require("path");
      const marker = path.join(process.env.UV_CACHE_DIR, "contenders"); fs.mkdirSync(marker, {recursive:true});
      fs.writeFileSync(path.join(marker, String(process.pid)), "ready");
      const wait = () => fs.readdirSync(marker).length >= 2 ? process.exit(0) : setTimeout(wait, 10); wait();
    `);
    const cacheDir = await mkdtemp(join(tmpdir(), "pi-science-cache-"));
    const options = {
      uv,
      cacheDir,
      revision: "immutable",
      repo: "https://example.invalid/repo.git",
      adapter: "/adapter.py",
    };
    const [first, second] = await Promise.all([
      provision(options),
      provision(options),
    ]);
    expect(first.ready).toBe(true);
    expect(second.ready).toBe(true);
  });

  it("makes concurrent provisioning failures fail closed with the same diagnosis", async () => {
    const uv = await fakeUv("process.exit(1)");
    const options = {
      uv,
      cacheDir: await mkdtemp(join(tmpdir(), "pi-science-cache-")),
      revision: "immutable",
      repo: "https://example.invalid/repo.git",
      adapter: "/adapter.py",
    };
    const states = await Promise.all([provision(options), provision(options)]);
    expect(states).toEqual([
      {
        ready: false,
        diagnosis:
          "Python formula environment could not be provisioned; install uv, then restart Pi to retry.",
      },
      {
        ready: false,
        diagnosis:
          "Python formula environment could not be provisioned; install uv, then restart Pi to retry.",
      },
    ]);
  });
});
