import { mkdtemp } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { describe, expect, it, vi } from "vitest";
import { resolvePinnedRevision, start } from "../src/index.js";

const repositoryRoot = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "../../..",
);

type Command = {
  handler(args: string, context: unknown): Promise<void>;
};
type Tool = {
  parameters: { properties: { expression: { maxLength?: number } } };
  execute(
    id: string,
    params: { expression: string },
    signal?: AbortSignal,
  ): Promise<{
    content: Array<{ type: string; text: string }>;
    details: unknown;
  }>;
};
type EventHandler = (event: unknown, context: unknown) => Promise<void>;

function host() {
  const commands = new Map<string, Command>();
  const tools: Tool[] = [];
  const events = new Map<string, EventHandler>();
  const api = {
    registerCommand: vi.fn((name: string, command: Command) => {
      commands.set(name, command);
    }),
    registerTool: vi.fn((tool: Tool) => {
      tools.push(tool);
    }),
    on: vi.fn((name: string, handler: EventHandler) => {
      events.set(name, handler);
    }),
  } as unknown as ExtensionAPI;
  return { api, commands, tools, events };
}

function context(hasUI: boolean) {
  return {
    hasUI,
    ui: { notify: vi.fn() },
  };
}

describe("readiness gate", () => {
  it("uses the real command signature and registers a valid tool result", async () => {
    const current = host();
    const response = {
      status: "success",
      interpretation: { normalized_sympy: "x", normalized_latex: "x" },
      operation_counts: {
        additions: 0,
        subtractions: 0,
        multiplications: 0,
        divisions: 0,
        powers: 0,
      },
      abstract_work: 0,
    };
    await start(
      current.api,
      Promise.resolve({
        ready: true,
        command: process.execPath,
        args: [
          "-e",
          `process.stdin.resume();process.stdin.on("end",()=>process.stdout.write(${JSON.stringify(
            JSON.stringify({ version: 1, result: response }),
          )}))`,
        ],
      }),
    );
    expect(current.commands.has("pi-science-doctor")).toBe(true);
    expect(current.tools).toHaveLength(1);
    expect(current.tools[0]?.parameters.properties.expression.maxLength).toBe(
      65_536,
    );
    const result = await current.tools[0]?.execute("id", { expression: "x" });
    expect(result).toEqual({
      content: [{ type: "text", text: JSON.stringify(response) }],
      details: response,
    });
  });

  it("warns once per disabled extension instance through UI and keeps doctor", async () => {
    const current = host();
    await start(
      current.api,
      Promise.resolve({ ready: false, diagnosis: "uv is missing" }),
    );
    expect(current.tools).toHaveLength(0);
    const notifyContext = context(true);
    const sessionStart = current.events.get("session_start");
    await sessionStart?.({}, notifyContext);
    await sessionStart?.({}, notifyContext);
    expect(notifyContext.ui.notify).toHaveBeenCalledOnce();

    const doctor = current.commands.get("pi-science-doctor");
    await doctor?.handler("", notifyContext);
    expect(notifyContext.ui.notify).toHaveBeenLastCalledWith(
      expect.stringContaining("Reload or restart"),
      "warning",
    );
  });

  it("uses stderr without UI and a new ready instance recovers", async () => {
    const stderr = vi
      .spyOn(process.stderr, "write")
      .mockImplementation(() => true);
    try {
      const disabled = host();
      await start(
        disabled.api,
        Promise.resolve({ ready: false, diagnosis: "provisioning failed" }),
      );
      await disabled.events.get("session_start")?.({}, context(false));
      await disabled.commands
        .get("pi-science-doctor")
        ?.handler("", context(false));
      expect(stderr).toHaveBeenCalled();

      const recovered = host();
      await start(
        recovered.api,
        Promise.resolve({ ready: true, command: "unused", args: [] }),
      );
      expect(recovered.tools).toHaveLength(1);
    } finally {
      stderr.mockRestore();
    }
  });

  it("derives only a full commit from the installed repository checkout", async () => {
    expect(resolvePinnedRevision(repositoryRoot)).toMatch(/^[0-9a-f]{40}$/);
    const nonRepository = await mkdtemp(join(tmpdir(), "pi-science-no-git-"));
    expect(resolvePinnedRevision(nonRepository)).toBeUndefined();
  });
});
