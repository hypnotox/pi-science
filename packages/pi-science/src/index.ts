import { execFile } from "node:child_process";
import { dirname } from "node:path";
import { promisify } from "node:util";
import { fileURLToPath } from "node:url";
import { invokeAdapter } from "./bridge.js";
import { provision, type Readiness } from "./provision.js";

type Pi = {
  registerTool(tool: unknown): void;
  registerCommand(command: unknown): void;
  on(event: string, handler: (...args: any[]) => void): void;
};
let warned = false;
export async function start(
  pi: Pi,
  readiness: Promise<Readiness>,
): Promise<void> {
  let state = await readiness;
  pi.registerCommand({
    name: "pi-science-doctor",
    description: "Show formula analysis readiness and recovery guidance",
    handler: () =>
      state.ready ? "Formula analysis is ready." : state.diagnosis,
  });
  if (!state.ready) {
    if (!warned) {
      console.error(`pi-science: ${state.diagnosis}`);
      warned = true;
    }
    return;
  }
  pi.registerTool({
    name: "analyze_formula",
    description: "Analyze restricted SymPy arithmetic without evaluating it",
    parameters: {
      type: "object",
      properties: { expression: { type: "string" } },
      required: ["expression"],
    },
    execute: async (
      _id: string,
      params: { expression: string },
      signal?: AbortSignal,
    ) =>
      invokeAdapter(
        state.command,
        state.args,
        { syntax: "sympy", expression: params.expression },
        10_000,
        signal,
      ),
  });
}
export default async function extension(pi: Pi): Promise<void> {
  const adapter = fileURLToPath(
    new URL("../bridge/formula_adapter.py", import.meta.url),
  );
  await start(
    pi,
    provision({
      revision: process.env.PI_SCIENCE_REVISION ?? "HEAD",
      repo: "https://github.com/hypnotox/pi-science.git",
      adapter,
    }),
  );
}
