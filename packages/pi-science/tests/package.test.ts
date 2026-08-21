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
    expect(skill).toContain("any returned field path, source span");
    expect(skill).toContain("proof qualifications");
    expect(skill).toContain("partial direct `closed_form` support");
    expect(skill).toContain("Sum(Sum(1, (l, -k, k)), (k, 0, p))");
    expect(skill).toContain(
      "distinct from the partial nested mathematical closed-form family",
    );
    expect(skill).toContain("compact human-readable projection");
    expect(skill).toContain("complete canonical report in `details`");
    expect(skill).toContain("complete replayable plans");
    expect(skill).toContain("first-ranked proved suggestion");
    expect(skill).toContain(
      "Keep plans atomic and do not combine separate candidates",
    );
    expect(skill).not.toContain("best proved");
    expect(skill).toContain("never a primary target");
    expect(skill).toContain(
      "Canonical `details` contains every plan and suggestion",
    );
    expect(skill).toContain(
      "evaluation work, not represented mathematical value",
    );
    expect(skill).toMatch(/unresolved query blocker[\s\S]+recovery hint/);
    expect(skill).toMatch(/Recovery hints[\s\S]+do not certify equivalence/);
    expect(skill).toMatch(
      /Recovery hints[\s\S]+do not[\s\S]+promise wider evaluator support/,
    );
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
            import { createRequire } from "node:module";
            import { writeFileSync } from "node:fs";
            import { discoverAndLoadExtensions } from "@earendil-works/pi-coding-agent";
            import { resolve } from "node:path";
            const extensionPath = resolve("node_modules/pi-science/packages/pi-science/src/index.ts");
            const adapter = resolve("node_modules/pi-science/packages/pi-science/bridge/formula_adapter.py");
            const probeExtension = resolve("formula-probe.ts");
            writeFileSync(
              probeExtension,
              "import { start } from " + JSON.stringify(extensionPath) + ";\\n" +
                "export default (pi) => start(pi, Promise.resolve({ ready: true, command: \\\"uv\\\", args: [\\\"run\\\", \\\"--project\\\", " +
                JSON.stringify(${JSON.stringify(root)}) +
                ", \\\"--locked\\\", \\\"python\\\", " + JSON.stringify(adapter) + "] }));\\n",
            );
            const loaded = await discoverAndLoadExtensions([probeExtension], process.cwd());
            if (loaded.errors.length !== 0) throw new Error(JSON.stringify(loaded.errors));
            if (loaded.extensions.length !== 1) throw new Error("formula extension was not loaded");
            const extension = loaded.extensions[0];
            if (!extension.commands.has("pi-science-doctor")) {
              throw new Error("formula extension did not register its diagnostic command");
            }
            const registered = extension.tools.get("analyze_formula");
            if (!registered) throw new Error("formula tool was not registered");
            const hostRequire = createRequire(import.meta.resolve("@earendil-works/pi-coding-agent"));
            const { Compile } = await import(hostRequire.resolve("typebox/compile"));
            const parameters = { expression: "x + 1", variables: { x: { domain: "real" } } };
            if (!Compile(registered.definition.parameters).Check(parameters)) {
              throw new Error("formula parameters failed host validation");
            }
            const result = await registered.definition.execute("id", parameters);
            if (result.details.status !== "success") {
              throw new Error("formula tool did not return success");
            }
            process.stdout.write("installed-formula-tool-invoked");
          `,
        ],
        { cwd: installed, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] },
      );
      expect(probe).toBe("installed-formula-tool-invoked");
    } finally {
      await rm(directory, { recursive: true, force: true });
      if (installed !== undefined)
        await rm(installed, { recursive: true, force: true });
    }
  }, 30_000);
});
