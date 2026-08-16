import { execFileSync } from "node:child_process";
import { mkdtemp } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");

describe("npm package boundary", () => {
  it("packs the required Pi sources under AGPL and production-installs externally", async () => {
    const directory = await mkdtemp(join(tmpdir(), "pi-science-pack-"));
    const packed = execFileSync(
      "npm",
      ["pack", "--json", "--pack-destination", directory],
      { cwd: root, encoding: "utf8" },
    );
    const tarball = join(directory, JSON.parse(packed)[0].filename as string);
    const files = execFileSync("tar", ["-tzf", tarball], { encoding: "utf8" })
      .trim()
      .split("\n");
    expect(files).toEqual(
      expect.arrayContaining([
        "package/package.json",
        "package/packages/pi-science/src/index.ts",
        "package/packages/pi-science/src/bridge.ts",
        "package/packages/pi-science/src/provision.ts",
        "package/packages/pi-science/src/process.ts",
        "package/packages/pi-science/bridge/formula_adapter.py",
      ]),
    );
    expect(
      JSON.parse(
        execFileSync("tar", ["-xOzf", tarball, "package/package.json"], {
          encoding: "utf8",
        }).toString(),
      ).license,
    ).toBe("AGPL-3.0-only");
    const installed = await mkdtemp(join(tmpdir(), "pi-science-install-"));
    execFileSync(
      "npm",
      ["install", "--omit=dev", "--ignore-scripts", tarball],
      { cwd: installed, stdio: "pipe" },
    );
  }, 30_000);
});
