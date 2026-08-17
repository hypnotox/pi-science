import { execFileSync } from "node:child_process";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");

describe("npm package boundary", () => {
  it("ships one complete uniquely named readiness-gated formula skill", async () => {
    const skill = await readFile(
      join(root, "packages/pi-science/skills/formula-analysis/SKILL.md"),
      "utf8",
    );
    expect(skill).toContain("name: pi-science-formula-analysis");
    expect(skill).toContain("analyze_formula");
    expect(skill).toContain("do not include `syntax` in a tool call");
    expect(skill).toContain("Sum(body, (index, lower, upper))");
    expect(skill).toContain("Parser acceptance, request-context validity");
    expect(skill).toContain("field path and source span");
    expect(skill).toContain("proof qualifications");
    expect(skill).toContain("py_science.formula");
    expect(skill).toContain("PEP 723");
    expect(skill).not.toContain("pi_science");
  });

  it("packs the required Pi sources under AGPL and production-installs externally", async () => {
    const directory = await mkdtemp(join(tmpdir(), "pi-science-pack-"));
    let installed: string | undefined;
    try {
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
          "package/packages/pi-science/src/formula-schema.json",
          "package/packages/pi-science/src/bridge.ts",
          "package/packages/pi-science/src/provision.ts",
          "package/packages/pi-science/src/process.ts",
          "package/packages/pi-science/bridge/formula_adapter.py",
          "package/packages/pi-science/skills/formula-analysis/SKILL.md",
        ]),
      );
      expect(
        JSON.parse(
          execFileSync("tar", ["-xOzf", tarball, "package/package.json"], {
            encoding: "utf8",
          }).toString(),
        ).license,
      ).toBe("AGPL-3.0-only");
      installed = await mkdtemp(join(tmpdir(), "pi-science-install-"));
      execFileSync(
        "npm",
        ["install", "--omit=dev", "--ignore-scripts", tarball],
        { cwd: installed, stdio: "pipe" },
      );
      const probe = execFileSync(
        process.execPath,
        [
          "--input-type=module",
          "--eval",
          `
            import { discoverAndLoadExtensions } from "@earendil-works/pi-coding-agent";
            import { resolve } from "node:path";
            const extensionPath = resolve("node_modules/pi-science/packages/pi-science/src/index.ts");
            const loaded = await discoverAndLoadExtensions([extensionPath], process.cwd());
            if (loaded.errors.length !== 0) throw new Error(JSON.stringify(loaded.errors));
            if (loaded.extensions.length !== 1) throw new Error("formula extension was not loaded");
            if (!loaded.extensions[0].commands.has("pi-science-doctor")) {
              throw new Error("formula extension did not register its diagnostic command");
            }
            process.stdout.write("installed-extension-loaded");
          `,
        ],
        { cwd: installed, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] },
      );
      expect(probe).toBe("installed-extension-loaded");
    } finally {
      await rm(directory, { recursive: true, force: true });
      if (installed !== undefined)
        await rm(installed, { recursive: true, force: true });
    }
  }, 30_000);
});
