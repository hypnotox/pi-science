import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import type {
  ExtensionAPI,
  ExtensionContext,
} from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { invokeAdapter, MAX_EXPRESSION_BYTES } from "./bridge.js";
import { provision, type Readiness } from "./provision.js";

const SHA = /^[0-9a-f]{40}$/;
const REPOSITORY_URL = "https://github.com/hypnotox/pi-science.git";
const formulaSchema = Type.Object(
  {
    expression: Type.String({
      description: "Restricted SymPy arithmetic expression",
      maxLength: MAX_EXPRESSION_BYTES,
    }),
  },
  { additionalProperties: false },
);

export function resolvePinnedRevision(
  repositoryRoot: string,
  git = "git",
): string | undefined {
  try {
    const revision = execFileSync(
      git,
      ["-C", repositoryRoot, "rev-parse", "--verify", "HEAD^{commit}"],
      { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] },
    ).trim();
    return SHA.test(revision) ? revision : undefined;
  } catch {
    return undefined;
  }
}

function toolResult(result: Record<string, unknown>) {
  return {
    content: [{ type: "text" as const, text: JSON.stringify(result) }],
    details: result,
  };
}

function report(context: ExtensionContext, text: string, ready: boolean): void {
  if (context.hasUI) context.ui.notify(text, ready ? "info" : "warning");
  else process.stderr.write(`pi-science: ${text}\n`);
}

export async function start(
  pi: ExtensionAPI,
  readiness: Promise<Readiness>,
): Promise<void> {
  const state = await readiness;
  pi.registerCommand("pi-science-doctor", {
    description:
      "Show formula analysis readiness and reload/restart recovery guidance",
    handler: async (_args, context) => {
      const text = state.ready
        ? "Formula analysis is ready."
        : `${state.diagnosis} Reload or restart Pi to retry provisioning.`;
      report(context, text, state.ready);
    },
  });

  if (!state.ready) {
    let warned = false;
    pi.on("session_start", async (_event, context) => {
      if (warned) return;
      warned = true;
      report(
        context,
        `${state.diagnosis} Reload or restart Pi to retry provisioning.`,
        false,
      );
    });
    return;
  }

  pi.registerTool({
    name: "analyze_formula",
    label: "Analyze formula",
    description: "Analyze restricted SymPy arithmetic without evaluating it",
    parameters: formulaSchema,
    async execute(_id, params, signal) {
      const result = await invokeAdapter(
        state.command,
        state.args,
        { syntax: "sympy", expression: params.expression },
        10_000,
        signal,
      );
      return toolResult(result);
    },
  });
}

export default async function extension(pi: ExtensionAPI): Promise<void> {
  const repositoryRoot = fileURLToPath(new URL("../../../", import.meta.url));
  const adapter = fileURLToPath(
    new URL("../bridge/formula_adapter.py", import.meta.url),
  );
  await start(
    pi,
    provision({
      revision: resolvePinnedRevision(repositoryRoot) ?? "",
      repo: REPOSITORY_URL,
      adapter,
      checkoutRoot: repositoryRoot,
    }),
  );
}
